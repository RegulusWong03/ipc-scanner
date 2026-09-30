"""海康威视 SADP 协议 — 广播发现设备与网络配置修改

SADP (Search Active Devices Protocol) 使用 UDP 组播:
- 组播地址: 239.255.255.250
- 端口: 37020
- 报文格式: XML over UDP
"""

import socket
import struct
import uuid
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)

SADP_MULTICAST_ADDR = "239.255.255.250"
SADP_PORT = 37020

# DeviceType 数值映射
DEVICE_TYPE_MAP = {
    "1": "IPC",
    "2": "NVR",
    "3": "Encoder",
    "4": "Decoder",
    "5": "AccessControl",
    "6": "VideoIntercom",
}

PROBE_XML = (
    '<?xml version="1.0" encoding="utf-8"?>'
    "<Probe>"
    "<Uuid>{uuid}</Uuid>"
    "<Types>inquiry</Types>"
    "</Probe>"
)

MODIFY_XML = (
    '<?xml version="1.0" encoding="utf-8"?>'
    "<ModifyDevice>"
    "<Uuid>{uuid}</Uuid>"
    "<MACAddress>{mac}</MACAddress>"
    "<DeviceMode>{mode}</DeviceMode>"
    "<Password>{password}</Password>"
    "<IPAddress>{ip}</IPAddress>"
    "<IPv4SubnetMask>{mask}</IPv4SubnetMask>"
    "<IPv4Gateway>{gateway}</IPv4Gateway>"
    "<DHCP>{dhcp}</DHCP>"
    "</ModifyDevice>"
)

ACTIVATE_XML = (
    '<?xml version="1.0" encoding="utf-8"?>'
    "<ActivateDevice>"
    "<Uuid>{uuid}</Uuid>"
    "<MACAddress>{mac}</MACAddress>"
    "<Password>{password}</Password>"
    "</ActivateDevice>"
)


class HikvisionSADP:
    """海康 SADP 协议实现"""

    def __init__(self, iface_ip: str | None = None):
        """
        Args:
            iface_ip: 指定绑定的本机 IP（多网卡场景），None 则自动选择
        """
        self.iface_ip = iface_ip
        self._sock: socket.socket | None = None

    def _create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)

        # 绑定到指定网卡
        if self.iface_ip:
            sock.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_MULTICAST_IF,
                socket.inet_aton(self.iface_ip),
            )

        sock.bind(("", SADP_PORT))

        # 加入组播组
        mreq = struct.pack(
            "4s4s",
            socket.inet_aton(SADP_MULTICAST_ADDR),
            socket.inet_aton(self.iface_ip or "0.0.0.0"),
        )
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except OSError as e:
            logger.warning("加入 SADP 组播组失败: %s", e)

        return sock

    def discover(self, timeout: float = 3.0) -> list[dict]:
        """发送 SADP Probe，发现局域网内的海康设备

        Returns:
            设备列表，每项包含:
            ip, mac, model, serial, firmware, device_type, subnet, gateway,
            dhcp, activated, factory_default, digital_channels, http_port, rtsp_port
        """
        sock = self._create_socket()
        sock.settimeout(timeout)

        msg_uuid = str(uuid.uuid4())
        probe = PROBE_XML.format(uuid=msg_uuid).encode("utf-8")

        try:
            sock.sendto(probe, (SADP_MULTICAST_ADDR, SADP_PORT))
        except OSError as e:
            logger.error("发送 SADP Probe 失败: %s", e)
            sock.close()
            return []

        devices = []
        seen_macs: set[str] = set()

        import time
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break

            device = self._parse_probe_match(data)
            if device is None:
                continue

            mac = device["mac"]
            if not mac or mac in seen_macs:
                continue
            seen_macs.add(mac)
            devices.append(device)

        sock.close()
        return devices

    def _parse_probe_match(self, data: bytes) -> dict | None:
        """解析 SADP ProbeMatch 响应"""
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            return None

        if root.tag != "ProbeMatch":
            return None

        mac = root.findtext("MACAddress", "").strip().lower()
        device_type_num = root.findtext("DeviceType", "").strip()

        return {
            "brand": "hikvision",
            "ip": root.findtext("IPAddress", "").strip(),
            "mac": mac,
            "model": root.findtext("DeviceDescription", "").strip(),
            "serial": root.findtext("DeviceSN", "").strip(),
            "firmware": root.findtext("DeviceVersion", "").strip(),
            "device_type": DEVICE_TYPE_MAP.get(device_type_num, "UNKNOWN"),
            "subnet": root.findtext("IPv4SubnetMask", "").strip(),
            "gateway": root.findtext("IPv4Gateway", "").strip(),
            "dhcp": root.findtext("DHCP", "false").strip().lower() == "true",
            "activated": root.findtext("Activate", "true").strip().lower() == "true",
            "factory_default": root.findtext("DeviceFactoryDefault", "false").strip().lower() == "true",
            "digital_channels": _int_safe(root.findtext("DigitalChannels", "0")),
            "analog_channels": _int_safe(root.findtext("AnalogChannels", "0")),
            "http_port": _int_safe(root.findtext("HttpPort", "80")),
            "rtsp_port": _int_safe(root.findtext("RtspPort", "554")),
            "device_port": _int_safe(root.findtext("DevicePort", "8000")),
        }

    def set_ip_config(self, mac: str, password: str,
                      new_ip: str, new_mask: str, new_gateway: str,
                      dhcp: bool = False, timeout: float = 5.0) -> dict:
        """通过 SADP 协议修改设备网络配置

        Args:
            mac: 设备 MAC 地址
            password: 设备密码（出厂默认 admin12345）
            new_ip: 新 IP 地址
            new_mask: 新子网掩码
            new_gateway: 新网关
            dhcp: 是否启用 DHCP

        Returns:
            {"success": bool, "message": str}
        """
        sock = self._create_socket()
        sock.settimeout(timeout)

        msg_uuid = str(uuid.uuid4())
        mode = "2" if dhcp else "1"
        xml = MODIFY_XML.format(
            uuid=msg_uuid,
            mac=mac,
            mode=mode,
            password=password,
            ip=new_ip,
            mask=new_mask,
            gateway=new_gateway,
            dhcp="true" if dhcp else "false",
        ).encode("utf-8")

        try:
            sock.sendto(xml, (SADP_MULTICAST_ADDR, SADP_PORT))
            data, _ = sock.recvfrom(65535)
            result = self._parse_modify_response(data)
            return result
        except socket.timeout:
            return {"success": False, "message": "超时：设备未响应"}
        except OSError as e:
            return {"success": False, "message": f"网络错误: {e}"}
        finally:
            sock.close()

    def _parse_modify_response(self, data: bytes) -> dict:
        """解析 ModifyDevice 响应"""
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            return {"success": False, "message": "响应解析失败"}

        result_code = root.findtext("ResultCode", "0").strip()
        result_msg = root.findtext("ResultMsg", "").strip()

        return {
            "success": result_code == "1",
            "message": result_msg or ("成功" if result_code == "1" else "失败"),
        }

    def activate_device(self, mac: str, password: str,
                        timeout: float = 5.0) -> dict:
        """激活未初始化的海康设备

        Args:
            mac: 设备 MAC 地址
            password: 要设置的管理员密码

        Returns:
            {"success": bool, "message": str}
        """
        sock = self._create_socket()
        sock.settimeout(timeout)

        msg_uuid = str(uuid.uuid4())
        xml = ACTIVATE_XML.format(
            uuid=msg_uuid, mac=mac, password=password,
        ).encode("utf-8")

        try:
            sock.sendto(xml, (SADP_MULTICAST_ADDR, SADP_PORT))
            data, _ = sock.recvfrom(65535)
            return self._parse_modify_response(data)
        except socket.timeout:
            return {"success": False, "message": "超时：设备未响应"}
        except OSError as e:
            return {"success": False, "message": f"网络错误: {e}"}
        finally:
            sock.close()


def _int_safe(value: str, default: int = 0) -> int:
    """安全地将字符串转为 int"""
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return default
