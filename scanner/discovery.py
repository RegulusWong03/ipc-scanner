"""设备发现模块 — 整合 WS-Discovery + 厂商广播 + 端口探测

扫描流程:
1. 并行执行 WS-Discovery、海康 SADP、大华 ConfigTool 广播发现
2. 对未识别的 IP 进行端口扫描
3. 通过 ARP 获取 MAC 地址（补充广播未覆盖的设备）
4. 通过 ONVIF 获取详细信息（可选，需认证）
5. 合并去重，以 MAC 为唯一键
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal

from scanner.port_scan import batch_scan, guess_brand
from scanner.network import resolve_mac_by_arp
from protocols.onvif_client import ws_discover, get_system_date_time, OnvifClient
from protocols.hikvision import HikvisionSADP
from protocols.dahua import DahuaConfigTool
from device.models import Device, DeviceStatus, DeviceType

logger = logging.getLogger(__name__)


class DeviceDiscoveryThread(QThread):
    """后台扫描线程

    通过 Qt 信号将发现的设备传回 UI:
    - device_found: 每发现一个设备就发出（实时显示）
    - scan_finished: 扫描结束后发出完整设备列表
    - scan_progress: 扫描进度更新
    - scan_error: 扫描出错信息
    """

    device_found = pyqtSignal(dict)
    scan_finished = pyqtSignal(list)
    scan_progress = pyqtSignal(int, int)  # current, total
    scan_error = pyqtSignal(str)

    def __init__(self, ip_list: list[str], iface_ip: str | None = None,
                 enable_onvif_detail: bool = False, parent=None):
        """
        Args:
            ip_list: 要端口扫描的 IP 列表
            iface_ip: 指定网卡 IP（用于广播/组播）
            enable_onvif_detail: 是否通过 ONVIF 获取详细信息（较慢，需认证）
        """
        super().__init__(parent)
        self.ip_list = ip_list
        self.iface_ip = iface_ip
        self.enable_onvif_detail = enable_onvif_detail
        self._is_running = True

    def run(self):
        devices_by_mac: dict[str, dict] = {}

        try:
            # === Phase 1: 广播发现（并行） ===
            logger.info("Phase 1: 广播发现...")
            broadcast_devices = self._run_broadcast_discovery(devices_by_mac)

            # === Phase 2: 端口扫描 ===
            if self._is_running:
                logger.info("Phase 2: 端口扫描 %d 个 IP...", len(self.ip_list))
                self._run_port_scan(devices_by_mac)

            # === Phase 3: 补充 MAC 地址 ===
            if self._is_running:
                logger.info("Phase 3: 补充 MAC 地址...")
                self._resolve_missing_macs(devices_by_mac)

            # === Phase 4: HTTP 探测（获取页面标题/Server 头） ===
            if self._is_running:
                logger.info("Phase 4: HTTP 探测...")
                self._run_http_probe(devices_by_mac)

            # === Phase 5: ONVIF 详细信息（可选） ===
            if self._is_running and self.enable_onvif_detail:
                logger.info("Phase 5: ONVIF 详细信息获取...")
                self._run_onvif_detail(devices_by_mac)

        except Exception as e:
            logger.error("扫描出错: %s", e)
            self.scan_error.emit(str(e))

        # 转换为 Device 对象列表（device_found 已在广播阶段发出，不再重复）
        result = []
        for mac, info in devices_by_mac.items():
            if not mac or mac == "00:00:00:00:00:00":
                continue
            device = self._build_device(info)
            result.append(device)

        self.scan_finished.emit(result)

    def stop(self):
        self._is_running = False

    def _run_broadcast_discovery(self, devices_by_mac: dict):
        """并行执行所有广播发现协议"""
        if not self._is_running:
            return

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {}

            # WS-Discovery
            futures[pool.submit(
                ws_discover, timeout=3.0, iface_ip=self.iface_ip
            )] = "onvif"

            # 海康 SADP
            sadp = HikvisionSADP(iface_ip=self.iface_ip)
            futures[pool.submit(sadp.discover, timeout=3.0)] = "hikvision"

            # 大华 ConfigTool
            dahua = DahuaConfigTool(iface_ip=self.iface_ip)
            futures[pool.submit(dahua.discover, timeout=3.0)] = "dahua"

            for future in as_completed(futures):
                if not self._is_running:
                    break
                protocol = futures[future]
                try:
                    found = future.result()
                    for d in found:
                        mac = d.get("mac", "")
                        if mac:
                            devices_by_mac[mac] = d
                            self.device_found.emit(d)
                    logger.info("  %s: 发现 %d 个设备", protocol, len(found))
                except Exception as e:
                    logger.warning("  %s 发现失败: %s", protocol, e)

    def _run_port_scan(self, devices_by_mac: dict):
        """对 IP 列表进行端口扫描，与广播结果合并"""
        # 获取广播已发现的 IP，跳过它们（已有详细信息）
        known_ips = {d.get("ip") for d in devices_by_mac.values()}

        # 过滤掉已知的 IP
        scan_ips = [ip for ip in self.ip_list if ip not in known_ips]
        if not scan_ips:
            return

        total = len(scan_ips)

        def on_progress(current, _total):
            if self._is_running:
                self.scan_progress.emit(current, total)

        results = batch_scan(
            scan_ips,
            timeout=0.3,
            max_workers=50,
            progress_callback=on_progress,
        )

        for r in results:
            ip = r["ip"]
            # 通过 ARP 获取 MAC
            mac = resolve_mac_by_arp(ip)
            if not mac:
                mac = f"unknown:{ip}"

            # 如果已有记录则合并，否则新建
            if mac in devices_by_mac:
                # 补充端口信息
                devices_by_mac[mac]["open_ports"] = r["open_ports"]
            else:
                open_ports = r["open_ports"]
                devices_by_mac[mac] = {
                    "ip": ip,
                    "mac": mac,
                    "brand": r.get("brand", ""),
                    "device_type": r.get("device_type", ""),
                    "open_ports": open_ports,
                    "http_port": _get_http_port(open_ports),
                    "rtsp_port": _get_port(open_ports, 554),
                    "device_port": _get_port(open_ports, 8000),
                    "tcp_port": _get_port(open_ports, 37777),
                }

    def _resolve_missing_macs(self, devices_by_mac: dict):
        """为没有真实 MAC 的设备尝试解析 MAC"""
        for mac_key, info in list(devices_by_mac.items()):
            if not self._is_running:
                break
            if mac_key.startswith("unknown:"):
                ip = info.get("ip", "")
                real_mac = resolve_mac_by_arp(ip)
                if real_mac and real_mac != "00:00:00:00:00:00":
                    info["mac"] = real_mac
                    devices_by_mac[real_mac] = info
                    del devices_by_mac[mac_key]

    def _run_onvif_detail(self, devices_by_mac: dict):
        """对支持 ONVIF 的设备获取详细信息"""
        for mac, info in devices_by_mac.items():
            if not self._is_running:
                break
            # 只处理未获取详细信息的设备
            if info.get("model") or info.get("serial"):
                continue

            ip = info.get("ip", "")
            port = info.get("http_port", 80)

            # 尝试 ONVIF 无认证调用获取系统时间
            service_url = f"http://{ip}:{port}/onvif/device_service"
            dt = get_system_date_time(service_url)
            if dt:
                info["onvif_available"] = True
                info["system_time"] = dt
                # 通过设备时间与当前时间差计算运行时间
                try:
                    from datetime import timezone
                    now = datetime.now(timezone.utc)
                    device_time = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                    delta = now - device_time
                    if delta.total_seconds() > 0:
                        days = delta.days
                        hours, remainder = divmod(delta.seconds, 3600)
                        minutes, _ = divmod(remainder, 60)
                        parts = []
                        if days > 0:
                            parts.append(f"{days}天")
                        if hours > 0:
                            parts.append(f"{hours}小时")
                        if minutes > 0:
                            parts.append(f"{minutes}分钟")
                        info["uptime"] = " ".join(parts) if parts else "< 1分钟"
                except Exception:
                    pass

            # 尝试用默认账密获取详细信息
            for user, pwd in [("admin", "admin"), ("admin", "12345"), ("admin", "")]:
                try:
                    client = OnvifClient(ip, port, user, pwd)
                    client.connect()
                    dev_info = client.get_device_info()
                    info.update({
                        "brand": info.get("brand", "") or dev_info.get("manufacturer", ""),
                        "model": dev_info.get("model", ""),
                        "firmware": dev_info.get("firmware_version", ""),
                        "serial": dev_info.get("serial_number", ""),
                    })
                    # 获取网络接口以补充 MAC
                    net_ifaces = client.get_network_interfaces()
                    for ni in net_ifaces:
                        if ni.get("mac"):
                            info["mac"] = ni["mac"]
                        if ni.get("dhcp"):
                            info["dhcp"] = True
                    client.close()
                    break
                except Exception:
                    continue

    def _run_http_probe(self, devices_by_mac: dict):
        """对开放 HTTP 端口的设备尝试获取页面标题和 Server 头"""
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {}
            for mac, info in devices_by_mac.items():
                if not self._is_running:
                    break
                # 已有 device_name 的跳过
                if info.get("device_name"):
                    continue
                ip = info.get("ip", "")
                http_port = info.get("http_port", 0) or _get_http_port(
                    info.get("open_ports", []))
                if http_port:
                    futures[pool.submit(self._http_probe, ip, http_port)] = mac

            for future in as_completed(futures):
                mac = futures[future]
                try:
                    result = future.result()
                    if result:
                        devices_by_mac[mac].update(result)
                except Exception:
                    pass

    def _http_probe(self, ip: str, port: int) -> dict:
        """尝试从 HTTP 页面获取设备名称和 Server 信息"""
        import urllib.request
        import re
        result = {}
        url = f"http://{ip}:{port}/"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                # 提取 Server 头
                server = resp.getheader("Server", "")
                if server:
                    result["mac_vendor"] = server
                # 读取 HTML 并提取 title
                html = resp.read(4096).decode("utf-8", errors="ignore")
                title_match = re.search(
                    r"<title>(.*?)</title>", html, re.IGNORECASE)
                if title_match:
                    result["device_name"] = title_match.group(1).strip()
        except Exception:
            pass
        return result

    def _build_device(self, info: dict) -> Device:
        """将扫描结果字典转为 Device 对象"""
        device_type_str = info.get("device_type", "UNKNOWN")
        try:
            device_type = DeviceType(device_type_str)
        except ValueError:
            device_type = DeviceType.UNKNOWN

        channels = info.get("digital_channels", 0) or info.get("channels", 0)

        return Device(
            mac=info.get("mac", ""),
            ip=info.get("ip", ""),
            subnet_mask=info.get("subnet", ""),
            gateway=info.get("gateway", ""),
            port=info.get("http_port", 80),
            device_type=device_type,
            brand=info.get("brand", ""),
            model=info.get("model", ""),
            firmware_version=info.get("firmware", ""),
            serial_number=info.get("serial", ""),
            channels=channels,
            status=DeviceStatus.ONLINE,
            dhcp=info.get("dhcp", False),
            http_port=info.get("http_port", 0),
            rtsp_port=info.get("rtsp_port", 0),
            device_port=info.get("device_port", 0),
            tcp_port=info.get("tcp_port", 0),
            analog_channels=info.get("analog_channels", 0),
            factory_default=info.get("factory_default", False),
            activated=info.get("activated", True),
            device_name=info.get("device_name", ""),
            mac_vendor=info.get("mac_vendor", ""),
            first_seen=datetime.now(),
            last_seen=datetime.now(),
        )


def _get_http_port(open_ports: list[dict]) -> int:
    """从开放端口列表中获取 HTTP 端口"""
    for p in open_ports:
        if p["port"] in (80, 8080, 443):
            return p["port"]
    return 80


def _get_port(open_ports: list[dict], target_port: int) -> int:
    """从开放端口列表中查找指定端口是否开放"""
    for p in open_ports:
        if p["port"] == target_port:
            return target_port
    return 0
