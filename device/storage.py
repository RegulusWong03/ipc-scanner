"""设备数据持久化 — SQLite 存储"""

import sqlite3
from pathlib import Path
from datetime import datetime
from .models import Device, DeviceStatus, DeviceType


DB_PATH = Path.home() / ".ipc-scanner" / "devices.db"

# 新增列定义（用于迁移旧数据库）
_MIGRATION_COLUMNS = [
    ("http_port", "INTEGER DEFAULT 0"),
    ("rtsp_port", "INTEGER DEFAULT 0"),
    ("device_port", "INTEGER DEFAULT 0"),
    ("tcp_port", "INTEGER DEFAULT 0"),
    ("analog_channels", "INTEGER DEFAULT 0"),
    ("factory_default", "INTEGER DEFAULT 0"),
    ("activated", "INTEGER DEFAULT 1"),
    ("device_name", "TEXT DEFAULT ''"),
    ("mac_vendor", "TEXT DEFAULT ''"),
]


def init_db():
    """初始化数据库表"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            mac TEXT PRIMARY KEY,
            ip TEXT,
            subnet_mask TEXT,
            gateway TEXT,
            port INTEGER,
            device_type TEXT,
            brand TEXT,
            model TEXT,
            firmware_version TEXT,
            serial_number TEXT,
            channels INTEGER,
            uptime TEXT,
            dhcp INTEGER,
            rtsp_url TEXT,
            device_group TEXT,
            note TEXT,
            first_seen TEXT,
            last_seen TEXT,
            http_port INTEGER DEFAULT 0,
            rtsp_port INTEGER DEFAULT 0,
            device_port INTEGER DEFAULT 0,
            tcp_port INTEGER DEFAULT 0,
            analog_channels INTEGER DEFAULT 0,
            factory_default INTEGER DEFAULT 0,
            activated INTEGER DEFAULT 1,
            device_name TEXT DEFAULT '',
            mac_vendor TEXT DEFAULT ''
        )
    """)
    conn.commit()
    # 迁移：为旧数据库添加缺失的列
    _migrate(conn)
    conn.close()


def _migrate(conn: sqlite3.Connection):
    """为已有的数据库表补充缺失的列"""
    cursor = conn.execute("PRAGMA table_info(devices)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    for col_name, col_type in _MIGRATION_COLUMNS:
        if col_name not in existing_cols:
            conn.execute(
                f"ALTER TABLE devices ADD COLUMN {col_name} {col_type}"
            )
    conn.commit()


def save_device(device: Device):
    """保存或更新设备记录"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO devices (mac, ip, subnet_mask, gateway, port, device_type,
            brand, model, firmware_version, serial_number, channels, uptime,
            dhcp, rtsp_url, device_group, note, first_seen, last_seen,
            http_port, rtsp_port, device_port, tcp_port,
            analog_channels, factory_default, activated,
            device_name, mac_vendor)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(mac) DO UPDATE SET
            ip=excluded.ip, subnet_mask=excluded.subnet_mask,
            gateway=excluded.gateway, port=excluded.port,
            device_type=excluded.device_type, brand=excluded.brand,
            model=excluded.model, firmware_version=excluded.firmware_version,
            serial_number=excluded.serial_number, channels=excluded.channels,
            uptime=excluded.uptime, dhcp=excluded.dhcp,
            rtsp_url=excluded.rtsp_url, last_seen=excluded.last_seen,
            http_port=excluded.http_port, rtsp_port=excluded.rtsp_port,
            device_port=excluded.device_port, tcp_port=excluded.tcp_port,
            analog_channels=excluded.analog_channels,
            factory_default=excluded.factory_default,
            activated=excluded.activated,
            device_name=excluded.device_name,
            mac_vendor=excluded.mac_vendor
    """, (
        device.mac, device.ip, device.subnet_mask, device.gateway,
        device.port, device.device_type.value, device.brand, device.model,
        device.firmware_version, device.serial_number, device.channels,
        device.uptime, int(device.dhcp), device.rtsp_url,
        device.group, device.note,
        device.first_seen.isoformat(), device.last_seen.isoformat(),
        device.http_port, device.rtsp_port, device.device_port,
        device.tcp_port, device.analog_channels,
        int(device.factory_default), int(device.activated),
        device.device_name, device.mac_vendor,
    ))
    conn.commit()
    conn.close()


def load_devices() -> list[Device]:
    """加载所有设备记录"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT * FROM devices").fetchall()
    conn.close()

    devices = []
    for row in rows:
        device = Device(
            mac=row[0], ip=row[1], subnet_mask=row[2] or "",
            gateway=row[3] or "", port=row[4],
            device_type=DeviceType(row[5]),
            brand=row[6] or "", model=row[7] or "",
            firmware_version=row[8] or "", serial_number=row[9] or "",
            channels=row[10] or 0, uptime=row[11] or "",
            dhcp=bool(row[12]), rtsp_url=row[13] or "",
            group=row[14] or "", note=row[15] or "",
            first_seen=datetime.fromisoformat(row[16]),
            last_seen=datetime.fromisoformat(row[17]),
            http_port=_int_or(row, 18),
            rtsp_port=_int_or(row, 19),
            device_port=_int_or(row, 20),
            tcp_port=_int_or(row, 21),
            analog_channels=_int_or(row, 22),
            factory_default=_bool_or(row, 23),
            activated=_bool_or(row, 24, default=True),
            device_name=_str_or(row, 25),
            mac_vendor=_str_or(row, 26),
        )
        device.status = DeviceStatus.OFFLINE
        devices.append(device)
    return devices


def update_device_note(mac: str, note: str):
    """更新设备备注"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE devices SET note=? WHERE mac=?", (note, mac))
    conn.commit()
    conn.close()


def update_device_group(mac: str, group: str):
    """更新设备分组"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE devices SET device_group=? WHERE mac=?", (group, mac))
    conn.commit()
    conn.close()


def _int_or(row: tuple, idx: int, default: int = 0) -> int:
    """安全地从行中读取整数值"""
    if idx < len(row) and row[idx] is not None:
        try:
            return int(row[idx])
        except (ValueError, TypeError):
            pass
    return default


def _bool_or(row: tuple, idx: int, default: bool = False) -> bool:
    """安全地从行中读取布尔值"""
    if idx < len(row) and row[idx] is not None:
        return bool(row[idx])
    return default


def _str_or(row: tuple, idx: int, default: str = "") -> str:
    """安全地从行中读取字符串值"""
    if idx < len(row) and row[idx] is not None:
        return str(row[idx])
    return default
