import json
import os
import datetime
from dataclasses import dataclass
from typing import Optional, List

import pandas as pd
from config import DATA_DIR, EXCEL_ENGINE, logger

# 中文星期与 Python weekday 映射
WEEKDAY_CN_TO_NUM = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6}

# 职称与技能等级映射
TITLE_TO_SKILL = {"主任医师": 3, "副主任医师": 2, "主治医师": 1, "住院医师": 0}

@dataclass
class StaffInfo:
    staff_id: str
    name: str
    role: str
    skill_level: int
    max_shifts: int
    available_dates: List[str]

@dataclass
class ShiftConfig:
    shift_id: str
    date: str
    shift_type: str
    required_skill: str
    required_level: int
    staff_needed: int


def fix_excel_date(date_val) -> str:
    """修复 Excel 日期序列号或 datetime 对象"""
    if isinstance(date_val, (int, float)):
        try:
            base = datetime.datetime(1899, 12, 30)
            return (base + datetime.timedelta(days=int(date_val))).strftime('%Y-%m-%d')
        except:
            return str(date_val)
    elif isinstance(date_val, (pd.Timestamp, datetime.datetime)):
        return date_val.strftime('%Y-%m-%d')
    else:
        return str(date_val)[:10]


def load_staff_info_from_json(
    path: str = "doctor_scheduling_data.json",
    shift_list: Optional[List[ShiftConfig]] = None,
) -> List[StaffInfo]:
    candidates = [
        os.path.join(DATA_DIR, path),
        path,
    ]
    full_path = next((p for p in candidates if os.path.exists(p)), None)
    if not full_path:
        logger.warning(f"JSON 文件不存在: {path}")
        return []

    with open(full_path, "r", encoding="utf-8") as f:
        doctors = json.load(f)

    staff_list = []
    all_dates = set(sh.date for sh in shift_list) if shift_list else set()
    if not all_dates:
        start = datetime.date(2024, 6, 1)
        all_dates = { (start + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30) }

    for doc in doctors:
        dept = doc.get("department", "")
        title = doc.get("title", "")
        role = f"{dept}-{title}" if dept and title else title or "未知"

        # 计算可用日期
        avail_days = doc.get("available_days", [])
        unavail = {item["date"] for item in doc.get("unavailable_time_ranges", [])}
        avail_dates = []
        for d in all_dates:
            dt = datetime.datetime.strptime(d, "%Y-%m-%d")
            weekday_cn = ["周一","周二","周三","周四","周五","周六","周日"][dt.weekday()]
            if weekday_cn in avail_days and d not in unavail:
                avail_dates.append(d)

        if not avail_dates:
            continue

        max_shifts = doc.get("max_shifts_per_week", 4) * 5  # 粗估5周

        staff_list.append(StaffInfo(
            staff_id=doc["doctor_id"],
            name=doc["name"],
            role=role,
            skill_level=TITLE_TO_SKILL.get(title, 0),
            max_shifts=max_shifts,
            available_dates=sorted(avail_dates)
        ))

    logger.info(f"从 JSON 加载了 {len(staff_list)} 名员工")
    return staff_list


def load_staff_info(filename: str = "staff_info.xlsx") -> List[StaffInfo]:
    full_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(full_path):
        logger.warning(f"员工文件不存在: {full_path}")
        return []

    df = pd.read_excel(full_path, engine=EXCEL_ENGINE)
    staff_list = []
    for _, row in df.iterrows():
        dates_str = row.get("available_dates", "")
        dates = [d.strip() for d in str(dates_str).split(",") if d.strip()] if dates_str else []
        staff_list.append(StaffInfo(
            staff_id=str(row["staff_id"]),
            name=str(row["name"]),
            role=str(row.get("role", "")),
            skill_level=int(row["skill_level"]),
            max_shifts=int(row["max_shifts"]),
            available_dates=dates
        ))
    return staff_list


def load_shift_config(filename: str = "shift_config.xlsx") -> List[ShiftConfig]:
    full_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(full_path):
        logger.warning(f"班次文件不存在: {full_path}")
        return []

    df = pd.read_excel(full_path, engine=EXCEL_ENGINE)
    shift_list = []
    for _, row in df.iterrows():
        date_str = fix_excel_date(row["date"])
        shift_list.append(ShiftConfig(
            shift_id=str(row["shift_id"]),
            date=date_str,
            shift_type=str(row["shift_type"]),
            required_skill=str(row["required_skill"]),
            required_level=int(row["required_level"]),
            staff_needed=int(row["staff_needed"])
        ))
    return shift_list


def save_staff_info(staff_list: List[StaffInfo], filename: str = "staff_info.xlsx"):
    full_path = os.path.join(DATA_DIR, filename)
    df = pd.DataFrame([
        {
            "staff_id": s.staff_id,
            "name": s.name,
            "role": s.role,
            "skill_level": s.skill_level,
            "max_shifts": s.max_shifts,
            "available_dates": ",".join(s.available_dates)
        } for s in staff_list
    ])
    df.to_excel(full_path, index=False, engine=EXCEL_ENGINE)
    logger.info(f"员工信息已保存到: {full_path}")