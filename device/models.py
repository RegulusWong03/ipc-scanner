"""设备数据模型"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class DeviceStatus(Enum):
    ONLINE = "在线"
    OFFLINE = "离线"
    NEW = "新上线"


class DeviceType(Enum):
    IPC = "IPC"
    NVR = "NVR"
    UNKNOWN = "未知"


@dataclass
class Device:
    """设备信息模型"""
    mac: str                          # MAC 地址（唯一标识）
    ip: str = ""
    subnet_mask: str = ""
    gateway: str = ""
    port: int = 80
    device_type: DeviceType = DeviceType.UNKNOWN
    brand: str = ""
    model: str = ""
    firmware_version: str = ""
    serial_number: str = ""
    channels: int = 0
    uptime: str = ""                  # 运行时间
    status: DeviceStatus = DeviceStatus.OFFLINE
    dhcp: bool = False
    rtsp_url: str = ""
    # 用户自定义
    group: str = ""                   # 分组（楼层/区域）
    note: str = ""                    # 备注名
    # 时间戳
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
