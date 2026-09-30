"""IP 冲突检测模块 — 通过 ARP 探测目标 IP 是否已被占用

提供两种检测方式:
1. scapy ARP（精确，需要 root/管理员权限）
2. ping + arp 缓存（轻量，跨平台兼容）
"""

import logging
import platform

logger = logging.getLogger(__name__)


def check_ip_conflict(target_ip: str, iface: str | None = None,
                      timeout: float = 1.0) -> dict:
    """检测目标 IP 是否存在冲突

    Args:
        target_ip: 要检测的 IP 地址
        iface: 指定网卡接口名（scapy 模式），None 则自动选择
        timeout: ARP 超时时间（秒）

    Returns:
        {
            "conflict": bool,       # True 表示 IP 已被占用
            "mac": str,             # 占用该 IP 的设备 MAC（如果冲突）
            "method": str,          # 使用的检测方法
            "error": str,           # 错误信息（如果有）
        }
    """
    # 先尝试 scapy ARP（精确但需要权限）
    result = _check_by_scapy(target_ip, iface, timeout)
    if result is not None:
        return result

    # 降级到 ping + arp 缓存
    return _check_by_ping(target_ip)


def _check_by_scapy(target_ip: str, iface: str | None, timeout: float) -> dict | None:
    """使用 scapy 发送 ARP 请求检测冲突"""
    try:
        from scapy.all import ARP, Ether, srp

        arp_request = ARP(pdst=target_ip)
        broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = broadcast / arp_request

        kwargs = {"timeout": timeout, "verbose": False}
        if iface:
            kwargs["iface"] = iface

        answered, _ = srp(packet, **kwargs)

        if answered:
            # 提取响应设备的 MAC
            mac = answered[0][1].hwsrc
            return {
                "conflict": True,
                "mac": mac,
                "method": "scapy_arp",
                "error": "",
            }
        else:
            return {
                "conflict": False,
                "mac": "",
                "method": "scapy_arp",
                "error": "",
            }

    except ImportError:
        logger.debug("scapy 未安装，降级到 ping 方式")
        return None
    except PermissionError:
        logger.debug("无权限发送 ARP 包，降级到 ping 方式")
        return None
    except Exception as e:
        logger.warning("scapy ARP 检测失败: %s", e)
        return None


def _check_by_ping(target_ip: str) -> dict:
    """通过 ping + arp 缓存检测冲突（轻量降级方案）"""
    from scanner.network import resolve_mac_by_arp

    mac = resolve_mac_by_arp(target_ip)

    return {
        "conflict": bool(mac),
        "mac": mac,
        "method": "ping_arp",
        "error": "",
    }


def batch_check_conflict(ip_list: list[str], iface: str | None = None,
                         timeout: float = 1.0,
                         progress_callback=None) -> list[dict]:
    """批量检测多个 IP 的冲突状态

    Args:
        ip_list: 要检测的 IP 列表
        iface: 网卡接口名
        timeout: ARP 超时
        progress_callback: 进度回调 callback(current, total, ip, conflict)

    Returns:
        每个 IP 的冲突检测结果列表
    """
    results = []
    total = len(ip_list)

    for i, ip in enumerate(ip_list):
        result = check_ip_conflict(ip, iface, timeout)
        result["ip"] = ip
        results.append(result)

        if progress_callback:
            progress_callback(i + 1, total, ip, result["conflict"])

    return results
