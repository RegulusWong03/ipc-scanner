"""RTSP URL 生成辅助模块 — 根据品牌生成标准 RTSP 地址"""


def generate_rtsp_url(brand: str, ip: str, channel: int = 1,
                      stream: str = "main", username: str = "admin",
                      password: str = "admin") -> str:
    """根据品牌生成 RTSP URL

    Args:
        brand: 品牌标识 (hikvision/dahua/uniview/tp-link 等)
        ip: 设备 IP 地址
        channel: 通道号（NVR 使用，IPC 默认为 1）
        stream: 码流类型 (main/sub/third)
        username: 用户名
        password: 密码

    Returns:
        RTSP URL 字符串
    """
    brand_lower = brand.lower() if brand else ""

    if brand_lower == "hikvision":
        return _hikvision_url(ip, channel, stream, username, password)
    elif brand_lower == "dahua":
        return _dahua_url(ip, channel, stream, username, password)
    elif brand_lower == "uniview":
        return _uniview_url(ip, channel, stream, username, password)
    elif brand_lower in ("tp-link", "tplink"):
        return _tplink_url(ip, channel, stream, username, password)
    else:
        # 通用 ONVIF 格式
        return _generic_url(ip, channel, username, password)


def _hikvision_url(ip: str, channel: int, stream: str,
                   username: str, password: str) -> str:
    """海康 RTSP URL 格式:
    rtsp://admin:password@ip:554/Streaming/Channels/{channel}{stream_id}
    其中 stream_id: main=01, sub=02, third=03
    """
    stream_id = {"main": "01", "sub": "02", "third": "03"}.get(stream, "01")
    return f"rtsp://{username}:{password}@{ip}:554/Streaming/Channels/{channel}{stream_id}"


def _dahua_url(ip: str, channel: int, stream: str,
               username: str, password: str) -> str:
    """大华 RTSP URL 格式:
    rtsp://admin:password@ip:554/cam/realmonitor?channel={channel}&subtype={stream}
    其中 subtype: main=0, sub=1, third=2
    """
    subtype = {"main": "0", "sub": "1", "third": "2"}.get(stream, "0")
    return f"rtsp://{username}:{password}@{ip}:554/cam/realmonitor?channel={channel}&subtype={subtype}"


def _uniview_url(ip: str, channel: int, stream: str,
                 username: str, password: str) -> str:
    """宇视 RTSP URL 格式:
    rtsp://admin:password@ip:554/unicast/c{channel}/s{stream}
    """
    stream_id = {"main": "0", "sub": "1", "third": "2"}.get(stream, "0")
    return f"rtsp://{username}:{password}@{ip}:554/unicast/c{channel}/s{stream_id}"


def _tplink_url(ip: str, channel: int, stream: str,
                username: str, password: str) -> str:
    """TP-LINK RTSP URL 格式:
    rtsp://admin:password@ip:554/stream{stream_id}
    """
    stream_id = {"main": "1", "sub": "2", "third": "3"}.get(stream, "1")
    return f"rtsp://{username}:{password}@{ip}:554/stream{stream_id}"


def _generic_url(ip: str, channel: int, username: str, password: str) -> str:
    """通用 RTSP URL 格式（ONVIF 标准）"""
    return f"rtsp://{username}:{password}@{ip}:554/onvif1"


def parse_rtsp_url(url: str) -> dict:
    """解析 RTSP URL 提取组件

    Returns:
        {
            "username": str,
            "password": str,
            "ip": str,
            "port": int,
            "path": str,
        }
    """
    import re

    # rtsp://user:pass@ip:port/path
    pattern = r"rtsp://([^:]+):([^@]+)@([^:]+):(\d+)(.*)"
    match = re.match(pattern, url)

    if not match:
        # 尝试无密码格式
        pattern2 = r"rtsp://([^@]+)@([^:]+):(\d+)(.*)"
        match2 = re.match(pattern2, url)
        if match2:
            return {
                "username": match2.group(1),
                "password": "",
                "ip": match2.group(2),
                "port": int(match2.group(3)),
                "path": match2.group(4),
            }
        return {}

    return {
        "username": match.group(1),
        "password": match.group(2),
        "ip": match.group(3),
        "port": int(match.group(4)),
        "path": match.group(5),
    }


def generate_multiple_urls(brand: str, ip: str, channel: int = 1,
                           username: str = "admin",
                           passwords: list[str] = None) -> list[str]:
    """生成多个可能的 RTSP URL（尝试不同密码）

    Args:
        brand: 品牌
        ip: IP 地址
        channel: 通道号
        username: 用户名
        passwords: 密码列表（留空使用常见默认密码）

    Returns:
        RTSP URL 列表
    """
    if passwords is None:
        passwords = ["admin", "12345", "admin123", ""]

    urls = []
    for pwd in passwords:
        url = generate_rtsp_url(brand, ip, channel, "main", username, pwd)
        urls.append(url)

    return urls
