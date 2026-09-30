"""大华 ConfigTool 协议 — 广播发现设备与网络配置修改

ConfigTool 使用 UDP 广播:
- 端口: 5050
- 目标: 255.255.255.255（受限广播）
- 报文格式: 二进制协议（小端序）
"""

import socket
import struct
import logging
import time

logger = logging.getLogger(__name__)

DAHUA_PORT = 5050
DAHUA_BROADCAST = "255.255.255.255"

# 协议头
HEADER_MAGIC = b"\xf3\x00"
MSG_TYPE_SEARCH = 0x0006       # 搜索发现
MSG_TYPE_MODIFY = 0x0001       # 修改配置
MSG_TYPE_INITIALIZE = 0x0002   # 初始化设备

# DeviceClass 数值映射
DEVICE_CLASS_MAP = {
    0x01: "IPC",
    0x02: "NVR",
    0x03: "SpeedDome",
    0x04: "DVR",
}


class DahuaConfigTool:
    """大华 ConfigTool 协议实现"""

    def __init__(self, iface_ip: str | None = None):
        """
        Args:
            iface_ip: 指定绑定的本机 IP（多网卡场景）
        """
        self.iface_ip = iface_ip

    def _create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if self.iface_ip:
            sock.bind((self.iface_ip, DAHUA_PORT))
        else:
            sock.bind(("", DAHUA_PORT))

        return sock

    def discover(self, timeout: float = 3.0, broadcast: str = DAHUA_BROADCAST) -> list[dict]:
        """发送广播探测，发现局域网内的大华设备

        Args:
            timeout: 等待响应的超时时间（秒）
            broadcast: 广播地址，默认为受限广播

        Returns:
            设备列表
        """
        sock = self._create_socket()
        sock.settimeout(timeout)

        # 构造 16 字节搜索探测包
        probe = struct.pack(
            "<2sH2s2sI4s",
            HEADER_MAGIC,   # 0xF3 0x00
            16,             # 包长度
            struct.pack("<H", MSG_TYPE_SEARCH),
            b"\x00\x00",    # 保留
            0,              # Session ID
            b"\x00" * 4,    # 保留
        )

        # 发送多次以提高可靠性
        for _ in range(3):
            try:
                sock.sendto(probe, (broadcast, DAHUA_PORT))
            except OSError as e:
                logger.error("发送大华探测包失败: %s", e)
                sock.close()
                return []
            time.sleep(0.1)

        devices = []
        seen_macs: set[str] = set()
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            device = self._parse_search_response(data, addr)
            if device is None:
                continue

            mac = device["mac"]
            if not mac or mac in seen_macs:
                continue
            seen_macs.add(mac)
            devices.append(device)

        sock.close()
        return devices

    def _parse_search_response(self, data: bytes, addr: tuple) -> dict | None:
        """解析 ConfigTool 搜索响应包"""
        # 校验包长度和头部
        if len(data) < 100:
            return None
        if data[0:2] != HEADER_MAGIC:
            return None

        try:
            # 解析响应字段（固定偏移）
            model = _extract_string(data, 16, 16)
            mac = _extract_mac(data, 32)
            device_ip = _extract_string(data, 38, 16)
            subnet = _extract_string(data, 54, 16)
            gateway = _extract_string(data, 70, 16)
            tcp_port = struct.unpack("<H", data[86:88])[0]
            http_port = struct.unpack("<H", data[88:90])[0]
            firmware = _extract_string(data, 90, 32)
            serial = _extract_string(data, 122, 32)

            channels = 0
            device_class = 0
            dhcp = False
            if len(data) > 158:
                channels = struct.unpack("<H", data[154:156])[0]
                device_class = struct.unpack("<H", data[156:158])[0]
            if len(data) > 174:
                dhcp = data[174] == 0x01

            return {
                "brand": "dahua",
                "ip": device_ip or addr[0],
                "mac": mac,
                "model": model,
                "serial": serial,
                "firmware": firmware,
                "device_type": DEVICE_CLASS_MAP.get(device_class, "UNKNOWN"),
                "subnet": subnet,
                "gateway": gateway,
                "dhcp": dhcp,
                "channels": channels,
                "tcp_port": tcp_port,
                "http_port": http_port,
            }

        except (struct.error, IndexError) as e:
            logger.warning("解析大华响应包失败: %s", e)
            return None

    def set_ip_config(self, mac: str, password: str,
                      new_ip: str, new_mask: str, new_gateway: str,
                      dhcp: bool = False, timeout: float = 5.0) -> dict:
        """通过 ConfigTool 协议修改设备网络配置

        Args:
            mac: 设备 MAC 地址
            password: 设备管理密码
            new_ip: 新 IP 地址
            new_mask: 新子网掩码
            new_gateway: 新网关
            dhcp: 是否启用 DHCP

        Returns:
            {"success": bool, "message": str}
        """
        sock = self._create_socket()
        sock.settimeout(timeout)

        mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
        dhcp_flag = 0x01 if dhcp else 0x00

        # 构造修改请求包
        packet = bytearray(256)
        # 头部
        packet[0:2] = HEADER_MAGIC
        struct.pack_into("<H", packet, 2, 128)  # 包长度
        struct.pack_into("<H", packet, 4, MSG_TYPE_MODIFY)
        packet[6:8] = b"\x00\x00"
        struct.pack_into("<I", packet, 8, 0)  # Session ID

        # 目标 MAC
        packet[16:22] = mac_bytes
        packet[22:32] = b"\x00" * 10

        # 密码
        pwd_bytes = password.encode("ascii")[:32]
        packet[32:32 + len(pwd_bytes)] = pwd_bytes

        # 新网络配置
        _pack_string(packet, 64, new_ip, 16)
        _pack_string(packet, 80, new_mask, 16)
        _pack_string(packet, 96, new_gateway, 16)
        packet[112] = dhcp_flag

        try:
            sock.sendto(bytes(packet[:128]), (DAHUA_BROADCAST, DAHUA_PORT))
            data, _ = sock.recvfrom(4096)
            return self._parse_modify_response(data)
        except socket.timeout:
            return {"success": False, "message": "超时：设备未响应"}
        except OSError as e:
            return {"success": False, "message": f"网络错误: {e}"}
        finally:
            sock.close()

    def _parse_modify_response(self, data: bytes) -> dict:
        """解析配置修改响应"""
        if len(data) < 16 or data[0:2] != HEADER_MAGIC:
            return {"success": False, "message": "无效响应"}

        msg_type = struct.unpack("<H", data[4:6])[0]
        # 结果码在 session ID 位置（偏移 8）
        result_code = struct.unpack("<I", data[8:12])[0] if len(data) > 12 else 1

        if result_code == 0:
            return {"success": True, "message": "配置修改成功"}
        else:
            return {"success": False, "message": f"修改失败 (错误码: {result_code})"}

    def get_broadcast_addr(self, iface_ip: str, iface_mask: str) -> str:
        """计算子网定向广播地址"""
        import ipaddress
        network = ipaddress.IPv4Network(f"{iface_ip}/{iface_mask}", strict=False)
        return str(network.broadcast_address)


def _extract_string(data: bytes, offset: int, length: int) -> str:
    """从二进制数据中提取 null 终止的 ASCII 字符串"""
    chunk = data[offset:offset + length]
    null_idx = chunk.find(b"\x00")
    if null_idx >= 0:
        chunk = chunk[:null_idx]
    return chunk.decode("ascii", errors="replace")


def _extract_mac(data: bytes, offset: int) -> str:
    """从二进制数据中提取 MAC 地址"""
    mac_bytes = data[offset:offset + 6]
    return ":".join(f"{b:02x}" for b in mac_bytes)


def _pack_string(packet: bytearray, offset: int, value: str, length: int):
    """将字符串写入 bytearray 的指定偏移位置，null 填充"""
    encoded = value.encode("ascii")[:length]
    packet[offset:offset + len(encoded)] = encoded
    # 剩余位置保持为 0x00（bytearray 初始化时已为 0）
