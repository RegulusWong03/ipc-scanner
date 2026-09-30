"""网络工具模块 — 多网卡枚举、IP段解析、MAC地址查询"""

import ipaddress
import socket
import psutil


def get_network_interfaces() -> list[dict]:
    """枚举本机所有可用网卡，返回名称、IP、子网掩码、广播地址等信息

    过滤掉 loopback (127.0.0.1) 和无效网卡
    """
    interfaces = []
    for name, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                iface = {
                    "name": name,
                    "ip": addr.address,
                    "netmask": addr.netmask or "255.255.255.0",
                }
                # 计算广播地址
                if addr.broadcast:
                    iface["broadcast"] = addr.broadcast
                else:
                    network = ipaddress.IPv4Network(
                        f"{addr.address}/{addr.netmask}", strict=False
                    )
                    iface["broadcast"] = str(network.broadcast_address)
                interfaces.append(iface)
    return interfaces


def get_scan_range(ip: str, netmask: str, max_hosts: int = 254) -> list[str]:
    """根据 IP 和子网掩码计算可扫描的 IP 列表

    对于大网段（如 /16），截断到 max_hosts 以避免扫描过慢
    """
    network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
    hosts = list(network.hosts())
    if len(hosts) > max_hosts:
        hosts = hosts[:max_hosts]
    return [str(host) for host in hosts]


def parse_ip_range(cidr: str) -> list[str]:
    """解析用户手动输入的 CIDR 格式 IP 段，如 192.168.1.0/24"""
    network = ipaddress.IPv4Network(cidr, strict=False)
    return [str(host) for host in network.hosts()]


def get_local_ip_for_target(target_ip: str) -> str:
    """获取本机访问目标 IP 时使用的本地 IP 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((target_ip, 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except OSError:
        return ""


def mac_to_bytes(mac: str) -> bytes:
    """将 MAC 地址字符串转为 6 字节，支持 : - 无分隔符等格式"""
    clean = mac.replace(":", "").replace("-", "").lower()
    return bytes.fromhex(clean)


def bytes_to_mac(data: bytes) -> str:
    """将 6 字节转为 aa:bb:cc:dd:ee:ff 格式的 MAC 地址"""
    return ":".join(f"{b:02x}" for b in data[:6])


def resolve_mac_by_arp(target_ip: str) -> str:
    """通过系统 ARP 缓存查询 IP 对应的 MAC 地址（轻量级）

    先 ping 目标触发 ARP，再从 arp 表读取
    """
    import subprocess
    import re
    import platform

    # 触发 ARP
    try:
        if platform.system() == "Windows":
            subprocess.run(
                ["ping", "-n", "1", "-w", "500", target_ip],
                capture_output=True, timeout=3,
            )
            result = subprocess.run(
                ["arp", "-a", target_ip],
                capture_output=True, text=True, timeout=3,
            )
        else:
            subprocess.run(
                ["ping", "-c", "1", "-W", "1", target_ip],
                capture_output=True, timeout=3,
            )
            result = subprocess.run(
                ["arp", "-n", target_ip],
                capture_output=True, text=True, timeout=3,
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""

    # 解析 MAC
    mac_pattern = re.compile(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}")
    match = mac_pattern.search(result.stdout)
    if match:
        return match.group(0).lower().replace("-", ":")
    return ""
