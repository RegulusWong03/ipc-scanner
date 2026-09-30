"""操作日志模块 — 记录所有操作并持久化到 SQLite"""

import sqlite3
from pathlib import Path
from datetime import datetime


LOG_DB_PATH = Path.home() / ".ipc-scanner" / "operations.db"


def init_log_db():
    """初始化日志数据库"""
    LOG_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(LOG_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS operation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            operation TEXT NOT NULL,
            device_mac TEXT,
            device_ip TEXT,
            detail TEXT,
            result TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_operation(operation: str, device_mac: str = "",
                  device_ip: str = "", detail: str = "", result: str = "success"):
    """记录一条操作日志"""
    conn = sqlite3.connect(LOG_DB_PATH)
    conn.execute("""
        INSERT INTO operation_log (timestamp, operation, device_mac, device_ip, detail, result)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), operation, device_mac, device_ip, detail, result))
    conn.commit()
    conn.close()


def query_logs(operation: str = "", device_mac: str = "",
               start_time: str = "", end_time: str = "",
               limit: int = 100) -> list[dict]:
    """查询操作日志，支持按操作类型、设备、时间范围筛选"""
    conn = sqlite3.connect(LOG_DB_PATH)
    conditions = []
    params = []

    if operation:
        conditions.append("operation = ?")
        params.append(operation)
    if device_mac:
        conditions.append("device_mac = ?")
        params.append(device_mac)
    if start_time:
        conditions.append("timestamp >= ?")
        params.append(start_time)
    if end_time:
        conditions.append("timestamp <= ?")
        params.append(end_time)

    where = " AND ".join(conditions) if conditions else "1=1"
    query = f"SELECT * FROM operation_log WHERE {where} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return [
        {"id": r[0], "timestamp": r[1], "operation": r[2],
         "device_mac": r[3], "device_ip": r[4], "detail": r[5], "result": r[6]}
        for r in rows
    ]
