"""数据导入导出模块 — Excel/CSV 格式 + 样式美化 + 导入校验 + 模板生成"""

import csv
import re
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from device.models import Device, DeviceType, DeviceStatus


# 导出字段定义
EXPORT_FIELDS = [
    "IP", "MAC", "设备类型", "品牌", "型号", "序列号", "固件版本",
    "通道数", "HTTP端口", "RTSP端口", "设备端口",
    "子网掩码", "网关", "DHCP", "激活状态",
    "运行时间", "设备名称", "分组", "备注",
]

# 导入必填字段
REQUIRED_IMPORT_FIELDS = {"mac", "ip"}


def export_excel(devices: list[Device], filepath: str, styled: bool = True):
    """导出设备清单为 Excel 文件

    Args:
        devices: 设备列表
        filepath: 输出路径
        styled: 是否应用样式（表头、列宽、筛选器）
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "设备清单"
    ws.append(EXPORT_FIELDS)

    # 填充数据
    for d in devices:
        ws.append([
            d.ip, d.mac, d.device_type.value, d.brand, d.model,
            d.serial_number, d.firmware_version, d.channels,
            d.http_port or "", d.rtsp_port or "", d.device_port or "",
            d.subnet_mask, d.gateway, "是" if d.dhcp else "否",
            "已激活" if d.activated else "未激活",
            d.uptime, d.device_name, d.group, d.note,
        ])

    if styled:
        _apply_excel_styles(ws, len(EXPORT_FIELDS), len(devices))

    wb.save(filepath)


def export_csv(devices: list[Device], filepath: str):
    """导出设备清单为 CSV 文件"""
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(EXPORT_FIELDS)
        for d in devices:
            writer.writerow([
                d.ip, d.mac, d.device_type.value, d.brand, d.model,
                d.serial_number, d.firmware_version, d.channels,
                d.http_port or "", d.rtsp_port or "", d.device_port or "",
                d.subnet_mask, d.gateway, "是" if d.dhcp else "否",
                "已激活" if d.activated else "未激活",
                d.uptime, d.device_name, d.group, d.note,
            ])


def generate_template(filepath: str):
    """生成空白导入模板（含示例数据说明）"""
    wb = Workbook()
    ws = wb.active
    ws.title = "设备清单模板"

    # 表头
    ws.append(EXPORT_FIELDS)
    _apply_excel_styles(ws, len(EXPORT_FIELDS), 0)

    # 示例行（带注释）
    ws.append([
        "192.168.1.100", "aa:bb:cc:dd:ee:ff", "IPC", "hikvision",
        "DS-2CD2142FWD", "", "", 1, 80, 554, 8000,
        "255.255.255.0", "192.168.1.1", "否", "已激活",
        "", "", "1F-大厅", "前台摄像头"
    ])

    # 说明注释
    note_row = len(EXPORT_FIELDS) + 3
    ws.cell(row=note_row, column=1, value="说明:").font = Font(bold=True)
    ws.cell(row=note_row + 1, column=1, value="• IP 和 MAC 为必填字段")
    ws.cell(row=note_row + 2, column=1, value="• MAC 格式: aa:bb:cc:dd:ee:ff 或 aa-bb-cc-dd-ee-ff")
    ws.cell(row=note_row + 3, column=1, value='• DHCP: 填写"是"或"否"，留空默认为否')
    ws.cell(row=note_row + 4, column=1, value="• 分组: 可选，用于设备分类管理（如 1F-大厅）")

    wb.save(filepath)


def import_excel(filepath: str) -> list[dict]:
    """从 Excel 文件导入设备清单"""
    wb = load_workbook(filepath)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    result = []
    for row in rows:
        if not row or not row[0]:
            continue
        result.append(_parse_import_row(row))
    return result


def import_csv(filepath: str) -> list[dict]:
    """从 CSV 文件导入设备清单"""
    result = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)  # 跳过表头
        for row in reader:
            if not row or not row[0]:
                continue
            result.append(_parse_import_row(row))
    return result


def validate_import_data(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """校验导入数据，分离有效行和错误行

    Returns:
        (valid_rows, error_rows) 错误行包含 error 字段说明原因
    """
    valid = []
    errors = []

    for i, row in enumerate(rows, start=2):  # 从第2行开始（表头占第1行）
        error_msgs = []

        # 检查必填字段
        mac = row.get("mac", "").strip()
        ip = row.get("ip", "").strip()

        if not mac:
            error_msgs.append("MAC 为空")
        elif not _is_valid_mac(mac):
            error_msgs.append(f"MAC 格式错误: {mac}")

        if not ip:
            error_msgs.append("IP 为空")
        elif not _is_valid_ip(ip):
            error_msgs.append(f"IP 格式错误: {ip}")

        # 检查可选字段格式
        subnet = row.get("subnet_mask", "")
        if subnet and not _is_valid_ip(subnet):
            error_msgs.append(f"子网掩码格式错误: {subnet}")

        gateway = row.get("gateway", "")
        if gateway and not _is_valid_ip(gateway):
            error_msgs.append(f"网关格式错误: {gateway}")

        row_copy = dict(row)
        row_copy["_row_num"] = i

        if error_msgs:
            row_copy["_errors"] = "; ".join(error_msgs)
            errors.append(row_copy)
        else:
            row_copy["mac"] = mac.lower()
            row_copy["ip"] = ip
            valid.append(row_copy)

    return valid, errors


def _parse_import_row(row) -> dict:
    """解析单行导入数据为字典"""
    def _get(idx, default=""):
        if len(row) > idx and row[idx] is not None:
            return str(row[idx])
        return default

    channels = 0
    try:
        if len(row) > 7 and row[7] is not None:
            channels = int(row[7])
    except (ValueError, TypeError):
        pass

    return {
        "ip": _get(0),
        "mac": _get(1),
        "device_type": _get(2, "未知"),
        "brand": _get(3),
        "model": _get(4),
        "serial_number": _get(5),
        "firmware_version": _get(6),
        "channels": channels,
        "subnet_mask": _get(11),
        "gateway": _get(12),
        "dhcp": _get(13) == "是" if len(row) > 13 else False,
        "uptime": _get(15),
        "group": _get(17),
        "note": _get(18),
    }


def _apply_excel_styles(ws, num_cols: int, num_rows: int):
    """应用 Excel 样式：表头、列宽、筛选器、冻结首行"""
    # 表头样式
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1976D2", end_color="1976D2", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")

    for col_idx in range(1, num_cols + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # 列宽自适应（根据内容长度估算）
    col_widths = [15, 20, 10, 12, 20, 25, 15, 8, 8, 8, 8, 15, 15, 8, 8, 15, 15, 15, 25]
    for col_idx, width in enumerate(col_widths, start=1):
        if col_idx <= num_cols:
            ws.column_dimensions[get_column_letter(col_idx)].width = width

    # 添加筛选器
    if num_rows > 0:
        ws.auto_filter.ref = f"A1:{get_column_letter(num_cols)}{num_rows + 1}"

    # 冻结首行
    ws.freeze_panes = "A2"


def _is_valid_mac(mac: str) -> bool:
    """验证 MAC 地址格式"""
    patterns = [
        r"^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$",  # aa:bb:cc:dd:ee:ff
        r"^[0-9a-fA-F]{12}$",  # aabbccddeeff
    ]
    return any(re.match(p, mac) for p in patterns)


def _is_valid_ip(ip: str) -> bool:
    """验证 IPv4 地址格式"""
    pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if not re.match(pattern, ip):
        return False
    parts = ip.split(".")
    return all(0 <= int(p) <= 255 for p in parts)
