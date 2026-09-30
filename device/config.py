"""设备配置模块 — 统一入口，按品牌自动路由到对应协议

支持的操作:
- 修改网络配置 (IP/子网/网关/DHCP)
- 修改登录密码
- 激活未初始化的海康设备
"""

import logging
from protocols.onvif_client import OnvifClient
from protocols.hikvision import HikvisionSADP
from protocols.dahua import DahuaConfigTool

logger = logging.getLogger(__name__)

# 常见品牌默认账密（按优先级排列）
DEFAULT_CREDENTIALS = {
    "hikvision": [("admin", "admin12345"), ("admin", "12345"), ("admin", "admin")],
    "dahua": [("admin", "admin"), ("admin", "")],
    "uniview": [("admin", "123456"), ("admin", "admin")],
    "onvif": [("admin", "admin"), ("admin", "12345"), ("admin", "")],
}


def modify_network_config(brand: str, ip: str, mac: str,
                           new_ip: str, new_mask: str, new_gateway: str,
                           dhcp: bool = False,
                           username: str = "", password: str = "",
                           iface_ip: str | None = None) -> bool:
    """统一入口：修改设备网络配置

    策略:
    1. 优先尝试 ONVIF（通用协议，需认证）
    2. 如果 ONVIF 失败，按品牌走厂商私有协议 (SADP/ConfigTool)
    3. 私有协议不需要设备登录，适合出厂设备

    Args:
        brand: 品牌标识 (hikvision/dahua/uniview/其他)
        ip: 设备当前 IP
        mac: 设备 MAC 地址
        new_ip: 新 IP
        new_mask: 新子网掩码
        new_gateway: 新网关
        dhcp: 是否启用 DHCP
        username: 登录用户名（可选，为空则使用默认）
        password: 登录密码（可选，为空则尝试默认账密）
        iface_ip: 本机网卡 IP（用于广播/组播）

    Returns:
        是否修改成功
    """
    # 尝试 ONVIF
    if _try_onvif_config(ip, mac, new_ip, new_mask, new_gateway, dhcp,
                          username, password):
        return True

    # 按品牌走私有协议
    brand_lower = brand.lower()
    if brand_lower == "hikvision":
        return _hikvision_config(mac, ip, new_ip, new_mask, new_gateway,
                                 dhcp, password, iface_ip)
    elif brand_lower == "dahua":
        return _dahua_config(mac, new_ip, new_mask, new_gateway,
                              dhcp, password, iface_ip)
    else:
        # 未知品牌：遍历所有已知协议尝试
        if _hikvision_config(mac, ip, new_ip, new_mask, new_gateway,
                              dhcp, password, iface_ip):
            return True
        if _dahua_config(mac, new_ip, new_mask, new_gateway,
                          dhcp, password, iface_ip):
            return True
        logger.warning("所有协议均失败: %s (%s)", ip, mac)
        return False


def change_password(brand: str, ip: str, old_password: str,
                    new_password: str, port: int = 80,
                    username: str = "admin") -> dict:
    """修改设备登录密码

    Args:
        brand: 品牌标识
        ip: 设备 IP
        old_password: 旧密码
        new_password: 新密码
        port: HTTP 端口
        username: 用户名

    Returns:
        {"success": bool, "message": str}
    """
    # 通过 ONVIF 修改密码（通用）
    try:
        client = OnvifClient(ip, port, username, old_password)
        client.connect()
        ok = client.set_password(new_password)
        client.close()
        if ok:
            return {"success": True, "message": "密码修改成功"}
    except Exception as e:
        logger.debug("ONVIF 改密失败 (%s): %s", ip, e)

    # 海康 ISAPI 改密
    brand_lower = brand.lower()
    if brand_lower == "hikvision":
        result = _hikvision_change_password(ip, port, username, old_password, new_password)
        if result["success"]:
            return result

    return {"success": False, "message": f"密码修改失败，请确认旧密码正确且设备在线"}


def activate_hikvision_device(mac: str, password: str,
                               iface_ip: str | None = None) -> dict:
    """激活未初始化的海康设备"""
    sadp = HikvisionSADP(iface_ip=iface_ip)
    return sadp.activate_device(mac, password)


# === 内部实现 ===

def _try_onvif_config(ip: str, mac: str, new_ip: str, new_mask: str,
                       new_gateway: str, dhcp: bool,
                       username: str, password: str) -> bool:
    """尝试通过 ONVIF 修改网络配置"""
    # 确定要尝试的账密列表
    creds = []
    if username and password:
        creds.append((username, password))
    creds.extend(DEFAULT_CREDENTIALS.get("onvif", []))

    for user, pwd in creds:
        try:
            client = OnvifClient(ip, 80, user, pwd)
            client.connect()
            net_ifaces = client.get_network_interfaces()
            if net_ifaces:
                token = net_ifaces[0]["token"]
                client.set_network_config(token, new_ip, new_mask, new_gateway, dhcp)
                client.close()
                return True
            client.close()
        except Exception as e:
            logger.debug("ONVIF 配置失败 (user=%s): %s", user, e)
            continue

    return False


def _hikvision_config(mac: str, current_ip: str, new_ip: str, new_mask: str,
                       new_gateway: str, dhcp: bool,
                       password: str | None, iface_ip: str | None) -> bool:
    """通过海康 SADP 修改网络配置"""
    # 尝试默认密码
    passwords = [password] if password else []
    passwords.extend([p for _, p in DEFAULT_CREDENTIALS.get("hikvision", [])])

    sadp = HikvisionSADP(iface_ip=iface_ip)
    for pwd in passwords:
        if pwd is None:
            continue
        try:
            result = sadp.set_ip_config(mac, pwd, new_ip, new_mask, new_gateway, dhcp)
            if result.get("success"):
                return True
        except Exception as e:
            logger.debug("SADP 改 IP 失败 (pwd=%s): %s", pwd[:3] + "***", e)

    return False


def _dahua_config(mac: str, new_ip: str, new_mask: str, new_gateway: str,
                   dhcp: bool, password: str | None, iface_ip: str | None) -> bool:
    """通过大华 ConfigTool 修改网络配置"""
    passwords = [password] if password else []
    passwords.extend([p for _, p in DEFAULT_CREDENTIALS.get("dahua", [])])

    configtool = DahuaConfigTool(iface_ip=iface_ip)
    for pwd in passwords:
        if pwd is None:
            continue
        try:
            result = configtool.set_ip_config(mac, pwd, new_ip, new_mask, new_gateway, dhcp)
            if result.get("success"):
                return True
        except Exception as e:
            logger.debug("ConfigTool 改 IP 失败 (pwd=%s): %s", pwd[:3] + "***", e)

    return False


def _hikvision_change_password(ip: str, port: int, username: str,
                                old_password: str, new_password: str) -> dict:
    """通过海康 ISAPI 修改密码"""
    import httpx

    url = f"http://{ip}:{port}/ISAPI/Security/users/1"
    headers = {"Content-Type": "application/xml"}
    xml_body = (
        f'<User version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">'
        f"<userName>{username}</userName>"
        f"<password>{new_password}</password>"
        f"</User>"
    )

    try:
        resp = httpx.put(
            url,
            content=xml_body,
            headers=headers,
            auth=(username, old_password),
            timeout=10.0,
        )
        if resp.status_code == 200:
            return {"success": True, "message": "密码修改成功"}
        else:
            return {"success": False, "message": f"ISAPI 返回 {resp.status_code}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
