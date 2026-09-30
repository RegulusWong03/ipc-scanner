"""宇视私有协议 — 设备发现与配置"""


class UniviewDiscovery:
    """宇视私有发现协议"""

    def discover(self, timeout: float = 3.0) -> list[dict]:
        """发现局域网内的宇视设备"""
        # TODO: 实现宇视发现协议
        return []

    def set_ip_config(self, mac: str, password: str,
                      new_ip: str, new_mask: str, new_gateway: str) -> bool:
        """修改宇视设备网络配置"""
        # TODO: 实现配置修改
        return False
