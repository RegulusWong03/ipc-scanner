"""端口扫描模块 — 探测 IPC/NVR 常用端口并识别品牌"""

import socket
import struct
from concurrent.futures import ThreadPoolExecutor, as_completed

# IPC/NVR 常见端口及其品牌关联
COMMON_PORTS = {
    80: "HTTP",
    443: "HTTPS",
    554: "RTSP",
    3702: "ONVIF Discovery",
    8000: "Hikvision",
    8080: "HTTP Alt",
    9000: "Hikvision Alt",
    37777: "Dahua",
    45000: "Uniview",
}

# 用于品牌指纹识别的端口组合
BRAND_SIGNATURES = {
    "hikvision": {80, 8000, 554},
    "dahua": {80, 37777, 554},
    "uniview": {80, 45000, 554},
    "tp-link": {80, 554, 2000},
}


def scan_port(ip: str, port: int, timeout: float = 0.3) -> bool:
    """检测单个端口是否开放"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((ip, port)) == 0
    except (socket.timeout, OSError):
        return False


def scan_ports(ip: str, ports: list[int] | None = None,
               timeout: float = 0.3, max_workers: int = 8) -> list[dict]:
    """并发扫描指定 IP 的多个端口

    Args:
        ip: 目标 IP 地址
        ports: 要扫描的端口列表，默认使用 COMMON_PORTS
        timeout: 连接超时（秒）
        max_workers: 并发线程数

    Returns:
        开放端口的列表，每项包含 port 和 service 字段
    """
    if ports is None:
        ports = list(COMMON_PORTS.keys())

    open_ports = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(scan_port, ip, p, timeout): p for p in ports}
        for future in as_completed(futures):
            port = futures[future]
            if future.result():
                open_ports.append({
                    "port": port,
                    "service": COMMON_PORTS.get(port, "Unknown"),
                })

    open_ports.sort(key=lambda x: x["port"])
    return open_ports


def guess_brand(open_ports: list[dict]) -> str:
    """根据开放的端口组合猜测设备品牌

    Returns:
        品牌标识字符串，如 'hikvision'、'dahua'，无法识别时返回 ''
    """
    port_set = {p["port"] for p in open_ports}

    best_brand = ""
    best_score = 0
    for brand, signature in BRAND_SIGNATURES.items():
        score = len(port_set & signature)
        if score > best_score:
            best_score = score
            best_brand = brand

    # 至少匹配 2 个端口才算有效识别
    return best_brand if best_score >= 2 else ""


def is_ipc_or_nvr(open_ports: list[dict]) -> str:
    """根据端口判断设备类型

    Returns:
        'IPC'、'NVR' 或 'UNKNOWN'
    """
    port_set = {p["port"] for p in open_ports}

    # RTSP 端口 (554) 基本确定是视频设备
    if 554 in port_set:
        # 海康 NVR 通常开放 8000 + 多通道特征
        # 大华 NVR 通常开放 37777
        # 简单判断：IPC 和 NVR 端口类似，后续通过协议进一步区分
        return "IPC"

    if port_set:
        return "UNKNOWN"
    return ""


def scan_host(ip: str, timeout: float = 0.3) -> dict:
    """扫描单个主机的所有关键端口，返回综合结果

    Returns:
        {
            "ip": str,
            "alive": bool,
            "open_ports": list,
            "brand": str,
            "device_type": str,
        }
    """
    open_ports = scan_ports(ip, timeout=timeout)
    return {
        "ip": ip,
        "alive": len(open_ports) > 0,
        "open_ports": open_ports,
        "brand": guess_brand(open_ports),
        "device_type": is_ipc_or_nvr(open_ports),
    }


def batch_scan(ip_list: list[str], timeout: float = 0.3,
               max_workers: int = 50, progress_callback=None) -> list[dict]:
    """批量扫描多个 IP

    Args:
        ip_list: 要扫描的 IP 列表
        timeout: 每个端口的超时时间
        max_workers: 并发线程数
        progress_callback: 进度回调 callback(current, total)

    Returns:
        存活设备的扫描结果列表
    """
    results = []
    total = len(ip_list)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(scan_host, ip, timeout): ip for ip in ip_list}
        done_count = 0
        for future in as_completed(futures):
            done_count += 1
            result = future.result()
            if result["alive"]:
                results.append(result)
            if progress_callback:
                progress_callback(done_count, total)

    return results
