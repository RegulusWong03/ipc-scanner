"""批量操作模块 — 批量改密、批量改IP + 冲突预检"""

import ipaddress
import logging

from device.config import modify_network_config, change_password
from device.models import Device

logger = logging.getLogger(__name__)


def batch_change_password(devices: list[Device], new_password: str,
                          old_password: str = "",
                          progress_callback=None) -> dict:
    """批量修改设备密码

    Args:
        devices: 要修改的设备列表
        new_password: 新密码
        old_password: 旧密码（留空则尝试常见默认密码）
        progress_callback: callback(current, total, mac, success, message)

    Returns:
        {"success": int, "failed": int, "details": [(mac, success, message)]}
    """
    result = {"success": 0, "failed": 0, "details": []}
    total = len(devices)

    for i, device in enumerate(devices):
        try:
            r = change_password(
                brand=device.brand,
                ip=device.ip,
                old_password=old_password,
                new_password=new_password,
                port=device.port,
            )
            ok = r.get("success", False)
            msg = r.get("message", "")
            if ok:
                result["success"] += 1
            else:
                result["failed"] += 1
            result["details"].append((device.mac, ok, msg))
        except Exception as e:
            result["failed"] += 1
            result["details"].append((device.mac, False, str(e)))
            msg = str(e)

        if progress_callback:
            progress_callback(i + 1, total, device.mac, ok, msg)

    return result


def batch_change_ip(devices: list[Device], start_ip: str,
                    subnet_mask: str = "255.255.255.0",
                    gateway: str = "",
                    password: str = "",
                    check_conflict: bool = True,
                    progress_callback=None) -> dict:
    """按规则批量分配 IP（起始 IP + 递增）

    Args:
        devices: 要修改的设备列表
        start_ip: 起始 IP 地址
        subnet_mask: 子网掩码
        gateway: 网关
        password: 设备密码（留空使用默认）
        check_conflict: 是否在修改前检测 IP 冲突
        progress_callback: callback(current, total, mac, new_ip, success, message)

    Returns:
        {"success": int, "failed": int, "skipped": int,
         "details": [(mac, old_ip, new_ip, success, message)]}
    """
    result = {"success": 0, "failed": 0, "skipped": 0, "details": []}
    total = len(devices)
    base_ip = ipaddress.IPv4Address(start_ip)

    for i, device in enumerate(devices):
        new_ip = str(base_ip + i)
        old_ip = device.ip

        # 冲突预检
        if check_conflict and new_ip != old_ip:
            from scanner.ip_conflict import check_ip_conflict
            conflict = check_ip_conflict(new_ip)
            if conflict.get("conflict"):
                msg = f"IP 冲突: {new_ip} 已被 {conflict.get('mac', '未知')} 占用"
                result["skipped"] += 1
                result["details"].append((device.mac, old_ip, new_ip, False, msg))
                if progress_callback:
                    progress_callback(i + 1, total, device.mac, new_ip, False, msg)
                continue

        # 修改 IP
        try:
            ok = modify_network_config(
                brand=device.brand,
                ip=device.ip,
                mac=device.mac,
                new_ip=new_ip,
                new_mask=subnet_mask,
                new_gateway=gateway,
                password=password,
            )
            if ok:
                device.ip = new_ip
                device.subnet_mask = subnet_mask
                device.gateway = gateway
                result["success"] += 1
                msg = "成功"
            else:
                result["failed"] += 1
                msg = "修改失败"
            result["details"].append((device.mac, old_ip, new_ip, ok, msg))
        except Exception as e:
            result["failed"] += 1
            result["details"].append((device.mac, old_ip, new_ip, False, str(e)))
            msg = str(e)

        if progress_callback:
            progress_callback(i + 1, total, device.mac, new_ip, ok, msg)

    return result


def batch_set_dhcp(devices: list[Device], enable_dhcp: bool,
                   password: str = "",
                   progress_callback=None) -> dict:
    """批量切换 DHCP/静态模式

    Args:
        devices: 设备列表
        enable_dhcp: True 开启 DHCP, False 关闭
        password: 设备密码
        progress_callback: callback(current, total, mac, success, message)

    Returns:
        {"success": int, "failed": int, "details": [(mac, success, message)]}
    """
    result = {"success": 0, "failed": 0, "details": []}
    total = len(devices)

    for i, device in enumerate(devices):
        try:
            ok = modify_network_config(
                brand=device.brand,
                ip=device.ip,
                mac=device.mac,
                new_ip=device.ip,
                new_mask=device.subnet_mask or "255.255.255.0",
                new_gateway=device.gateway or "",
                dhcp=enable_dhcp,
                password=password,
            )
            if ok:
                device.dhcp = enable_dhcp
                result["success"] += 1
                msg = "成功"
            else:
                result["failed"] += 1
                msg = "修改失败"
            result["details"].append((device.mac, ok, msg))
        except Exception as e:
            result["failed"] += 1
            result["details"].append((device.mac, False, str(e)))
            msg = str(e)

        if progress_callback:
            progress_callback(i + 1, total, device.mac, ok, msg)

    return result
