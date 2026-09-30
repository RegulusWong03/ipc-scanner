"""ONVIF 协议客户端 — 标准协议交互

包含两个层次:
1. 轻量 WS-Discovery（仅 stdlib）：用于发现设备，不依赖 onvif-zeep
2. 完整 ONVIF 客户端（onvif-zeep）：用于认证后的服务调用
"""

import socket
import uuid
import time
import xml.etree.ElementTree as ET
import logging
from urllib.parse import urlparse
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ============================================================
# 轻量 WS-Discovery（不依赖 onvif-zeep）
# ============================================================

WS_MULTICAST = "239.255.255.250"
WS_PORT = 3702

NS = {
    "s":  "http://www.w3.org/2003/05/soap-envelope",
    "d":  "http://schemas.xmlsoap.org/ws/2005/04/discovery",
    "a":  "http://schemas.xmlsoap.org/ws/2004/08/addressing",
    "dn": "http://www.onvif.org/ver10/network/wsdl/RemoteDiscoveryBinding",
}

PROBE_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"'
    ' xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"'
    ' xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"'
    ' xmlns:dn="http://www.onvif.org/ver10/network/wsdl/RemoteDiscoveryBinding">'
    '<e:Header>'
    '<w:MessageID>uuid:{msg_id}</w:MessageID>'
    '<w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>'
    '<w:Action e:mustUnderstand="true">'
    'http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>'
    '</e:Header>'
    '<e:Body>'
    '<d:Probe><d:Types>{types}</d:Types></d:Probe>'
    '</e:Body></e:Envelope>'
)

# ONVIF 设备类型
ONVIF_TYPE_ALL = ""  # 发现所有 WS-Discovery 设备
ONVIF_TYPE_CAMERA = "dn:NetworkVideoTransmitter"
ONVIF_TYPE_NVR = "dn:NetworkVideoRecorder"


@dataclass
class DiscoveredOnvifDevice:
    """WS-Discovery 发现的设备"""
    ip: str
    port: int = 80
    service_url: str = ""
    scopes: list[str] = field(default_factory=list)
    endpoint_uuid: str = ""


def ws_discover(timeout: float = 3.0,
                device_type: str = ONVIF_TYPE_ALL,
                iface_ip: str | None = None) -> list[DiscoveredOnvifDevice]:
    """通过 WS-Discovery 发现 ONVIF 设备（仅用 stdlib）

    Args:
        timeout: 等待响应的超时（秒）
        device_type: 设备类型过滤，空字符串表示全部
        iface_ip: 指定网卡 IP

    Returns:
        发现的设备列表
    """
    msg_id = str(uuid.uuid4())
    probe_xml = PROBE_TEMPLATE.format(msg_id=msg_id, types=device_type)
    probe_bytes = probe_xml.encode("utf-8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(timeout)
    sock.bind(("", 0))  # 绑定随机端口接收单播响应

    # 指定发送网卡
    if iface_ip:
        sock.setsockopt(
            socket.IPPROTO_IP,
            socket.IP_MULTICAST_IF,
            socket.inet_aton(iface_ip),
        )

    try:
        sock.sendto(probe_bytes, (WS_MULTICAST, WS_PORT))
    except OSError as e:
        logger.error("WS-Discovery 发送失败: %s", e)
        sock.close()
        return []

    seen_endpoints: set[str] = set()
    devices: list[DiscoveredOnvifDevice] = []
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError:
            break

        parsed = _parse_probe_match(data)
        if parsed is None:
            continue

        ep = parsed["endpoint"]
        if ep in seen_endpoints:
            continue
        seen_endpoints.add(ep)

        xaddrs = parsed["xaddrs"]
        if xaddrs:
            ip, port = _extract_ip_port(xaddrs[0])
            if ip:
                devices.append(DiscoveredOnvifDevice(
                    ip=ip,
                    port=port,
                    service_url=xaddrs[0],
                    scopes=parsed["scopes"],
                    endpoint_uuid=ep,
                ))

    sock.close()
    return devices


def _parse_probe_match(data: bytes) -> dict | None:
    """解析 WS-Discovery ProbeMatch 响应"""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None

    match = root.find(".//d:ProbeMatch", NS)
    if match is None:
        return None

    xaddrs_text = match.findtext("d:XAddrs", "", NS)
    scopes_text = match.findtext("d:Scopes", "", NS)
    addr_text = match.findtext(".//a:Address", "", NS)

    return {
        "xaddrs": xaddrs_text.split(),
        "scopes": scopes_text.split(),
        "endpoint": addr_text,
    }


def _extract_ip_port(xaddr: str) -> tuple[str, int]:
    """从服务 URL 提取 IP 和端口"""
    try:
        parsed = urlparse(xaddr)
        return parsed.hostname or "", parsed.port or 80
    except Exception:
        return "", 80


# ============================================================
# ONVIF 无认证操作（通过 httpx 发 raw SOAP）
# ============================================================

def get_system_date_time(service_url: str, timeout: float = 5.0) -> dict | None:
    """调用 ONVIF GetSystemDateAndTime（无需认证）

    Returns:
        {"year", "month", "day", "hour", "minute", "second"} 或 None
    """
    import httpx

    soap_body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"'
        ' xmlns:tds="http://www.onvif.org/ver10/device/wsdl">'
        '<s:Body><tds:GetSystemDateAndTime/></s:Body>'
        '</s:Envelope>'
    )

    try:
        resp = httpx.post(
            service_url,
            content=soap_body,
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None
    except (httpx.HTTPError, httpx.TimeoutException):
        return None

    return _parse_system_date_time(resp.text)


def _parse_system_date_time(xml_text: str) -> dict | None:
    """解析 GetSystemDateAndTime 响应"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    tds_ns = "http://www.onvif.org/ver10/device/wsdl"

    utc = root.find(f".//{{{tds_ns}}}UTCDateTime")
    if utc is None:
        return None

    def _get(tag: str) -> int:
        el = utc.find(f".//{{{tds_ns}}}{tag}")
        if el is not None and el.text:
            return int(el.text)
        return 0

    return {
        "year": _get("Year"),
        "month": _get("Month"),
        "day": _get("Day"),
        "hour": _get("Hour"),
        "minute": _get("Minute"),
        "second": _get("Second"),
    }


# ============================================================
# 完整 ONVIF 客户端（需要 onvif-zeep，用于认证操作）
# ============================================================

class OnvifClient:
    """封装 ONVIF 认证操作（获取详细信息、修改配置、获取 RTSP 等）"""

    def __init__(self, ip: str, port: int = 80, user: str = "admin", password: str = "admin"):
        self.ip = ip
        self.port = port
        self.user = user
        self.password = password
        self._camera = None

    def connect(self):
        """连接 ONVIF 设备"""
        from onvif import ONVIFCamera
        self._camera = ONVIFCamera(self.ip, self.port, self.user, self.password)
        return self

    def get_device_info(self) -> dict:
        """获取设备详细信息：型号、固件版本、序列号等"""
        if not self._camera:
            raise ConnectionError("未连接设备")
        devicemgmt = self._camera.create_devicemgmt_service()
        info = devicemgmt.GetDeviceInformation()
        return {
            "manufacturer": info.Manufacturer,
            "model": info.Model,
            "firmware_version": info.FirmwareVersion,
            "serial_number": info.SerialNumber,
            "hardware_id": info.HardwareId,
        }

    def get_network_interfaces(self) -> list[dict]:
        """获取设备网络接口配置"""
        if not self._camera:
            raise ConnectionError("未连接设备")
        devicemgmt = self._camera.create_devicemgmt_service()
        interfaces = devicemgmt.GetNetworkInterfaces()
        result = []
        for iface in interfaces:
            ip_addr = None
            dhcp_enabled = False
            if iface.IPv4:
                config = iface.IPv4.Config
                if config.FromDHCP:
                    ip_addr = str(config.FromDHCP.Address)
                    dhcp_enabled = True
                elif config.Manual:
                    ip_addr = str(config.Manual[0].Address)
            result.append({
                "token": iface.token,
                "enabled": iface.Enabled,
                "mac": str(iface.Info.HwAddress),
                "ip": ip_addr,
                "dhcp": dhcp_enabled,
            })
        return result

    def set_network_config(self, interface_token: str, ip: str, mask: str,
                           gateway: str, dhcp: bool = False):
        """修改设备网络配置"""
        if not self._camera:
            raise ConnectionError("未连接设备")
        devicemgmt = self._camera.create_devicemgmt_service()

        if dhcp:
            # 切换到 DHCP 模式
            devicemgmt.SetNetworkInterfaces(
                InterfaceToken=interface_token,
                NetworkInterface={
                    "Enabled": True,
                    "IPv4": {"Enabled": True, "DHCP": True},
                },
            )
        else:
            # 切换到静态 IP
            devicemgmt.SetNetworkInterfaces(
                InterfaceToken=interface_token,
                NetworkInterface={
                    "Enabled": True,
                    "IPv4": {
                        "Enabled": True,
                        "DHCP": False,
                        "Manual": {
                            "Address": ip,
                            "PrefixLength": _mask_to_prefix(mask),
                        },
                    },
                },
            )
            # 设置网关
            if gateway:
                devicemgmt.SetNetworkProtocols()  # 部分设备需要此调用

    def set_password(self, new_password: str) -> bool:
        """修改设备用户密码"""
        if not self._camera:
            raise ConnectionError("未连接设备")
        try:
            devicemgmt = self._camera.create_devicemgmt_service()
            devicemgmt.SetUser({
                "User": {
                    "Username": self.user,
                    "Password": new_password,
                    "UserLevel": "Administrator",
                }
            })
            return True
        except Exception as e:
            logger.error("修改密码失败: %s", e)
            return False

    def get_rtsp_uri(self, channel: int = 0) -> str:
        """获取 RTSP 流地址"""
        if not self._camera:
            raise ConnectionError("未连接设备")
        media = self._camera.create_media_service()
        profiles = media.GetProfiles()
        if profiles and channel < len(profiles):
            token = profiles[channel].token
            stream_setup = {
                "Stream": "RTP-Unicast",
                "Transport": {"Protocol": "RTSP"},
            }
            uri = media.GetStreamUri({
                "StreamSetup": stream_setup,
                "ProfileToken": token,
            })
            return uri.Uri
        return ""

    def get_system_date_and_time(self) -> dict:
        """获取设备系统时间"""
        if not self._camera:
            raise ConnectionError("未连接设备")
        devicemgmt = self._camera.create_devicemgmt_service()
        dt = devicemgmt.GetSystemDateAndTime()
        return {
            "year": dt.UTCDateTime.Date.Year,
            "month": dt.UTCDateTime.Date.Month,
            "day": dt.UTCDateTime.Date.Day,
            "hour": dt.UTCDateTime.Time.Hour,
            "minute": dt.UTCDateTime.Time.Minute,
            "second": dt.UTCDateTime.Time.Second,
        }

    def close(self):
        self._camera = None


def _mask_to_prefix(mask: str) -> int:
    """将子网掩码转为前缀长度，如 255.255.255.0 -> 24"""
    import ipaddress
    return ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen
