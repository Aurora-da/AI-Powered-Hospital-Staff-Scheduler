"""
智能技能模块 - 为排班系统增强的 5 大智能技能
1. 冲突检测与预警 - 自动检测排班冲突并给出修复建议
2. 紧急代班 - 当有人请假/生病时，快速找到替代人员
3. 工作量均衡分析 - 分析和报告员工工作量分布
4. 排班质量评估 - 评估排班表质量并给出改进建议
5. 偏好学习 - 学习并记录员工的排班偏好
"""
import json
import os
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter, defaultdict
from ortools.sat.python import cp_model

from config import DATA_DIR, logger, SHIFT_KEYWORDS, MAX_NIGHT_SHIFTS_PER_PERSON, MAX_CONSECUTIVE_SHIFTS, PREFERENCE_EXTRACT_PROMPT
from excel_loader import load_staff_info, load_shift_config, StaffInfo, ShiftConfig
from llm_client import chat

# ============================================================
# 全局偏好存储
# ============================================================
@dataclass
class StaffPreference:
    """员工排班偏好"""
    staff_name: str
    preferred_dates: list[str] = field(default_factory=list)   # 偏好上班日期
    avoided_dates: list[str] = field(default_factory=list)     # 避免上班日期
    preferred_shifts: list[str] = field(default_factory=list)  # 偏好班次类型
    notes: str = ""

# 内存中的偏好存储（持久化可改为文件/数据库）
staff_preferences: dict[str, StaffPreference] = {}


# ============================================================
# 技能 1：冲突检测与预警
# ============================================================
def detect_conflicts() -> str:
    """检测当前排班表中的所有冲突并给出建议"""
    try:
        schedule_df = pd.read_excel(os.path.join(DATA_DIR, "schedule_result.xlsx"), engine="openpyxl")
    except FileNotFoundError:
        return "未找到排班结果文件，请先生成排班"

    conflicts = []
    staff_list, shift_list = load_staff_info("staff_info.xlsx"), load_shift_config("shift_config.xlsx")

    # 1. 连续排班检测
    for staff, group in schedule_df.groupby("staff"):
        dates = sorted(pd.to_datetime(group["date"]))
        consecutive = 1
        for i in range(1, len(dates)):
            if (dates[i] - dates[i - 1]).days == 1:
                consecutive += 1
                if consecutive > MAX_CONSECUTIVE_SHIFTS:
                    conflicts.append({
                        "type": "连续排班",
                        "severity": "高",
                        "detail": f"{staff} 连续排班 {consecutive} 天",
                        "suggestion": f"建议在 {dates[i-2].strftime('%Y-%m-%d')} 安排休息"
                    })
            else:
                consecutive = 1

    # 2. 班次分布不均检测
    shift_counts = schedule_df.groupby("staff").size()
    avg_shifts = shift_counts.mean()
    for staff, count in shift_counts.items():
        if count > avg_shifts * 1.5:
            conflicts.append({
                "type": "工作量过高",
                "severity": "中",
                "detail": f"{staff} 排班 {count} 次，高于平均值 {avg_shifts:.1f}",
                "suggestion": "建议将部分班次分配给工作量较低的员工"
            })
        elif count < avg_shifts * 0.5:
            conflicts.append({
                "type": "工作量过低",
                "severity": "低",
                "detail": f"{staff} 仅排班 {count} 次，低于平均值 {avg_shifts:.1f}",
                "suggestion": "可适当增加该员工班次"
            })

    # 3. 夜班密集检测
    night_shifts = schedule_df[schedule_df["shift_type"] == "夜班"]
    for staff, group in night_shifts.groupby("staff"):
        if len(group) > MAX_NIGHT_SHIFTS_PER_PERSON:
            conflicts.append({
                "type": "夜班过多",
                "severity": "高",
                "detail": f"{staff} 夜班 {len(group)} 次",
                "suggestion": "建议限制每人夜班次数，确保公平分配"
            })

    # 4. 技能不匹配检测
    for _, row in schedule_df.iterrows():
        staff_info = next((s for s in staff_list if s.name == row["staff"]), None)
        shift_info = next((s for s in shift_list if s.shift_id == row["shift_id"]), None)
        if staff_info and shift_info and staff_info.skill_level < shift_info.required_level:
            conflicts.append({
                "type": "技能不匹配",
                "severity": "高",
                "detail": f"{row['staff']} 技能等级 {staff_info.skill_level} 不足以胜任 {row['shift_type']}",
                "suggestion": f"需要技能等级 >= {shift_info.required_level} 的员工"
            })

    if not conflicts:
        return "恭喜！当前排班表未发现冲突，排班质量良好。"

    msg = f"冲突检测报告（共 {len(conflicts)} 项）：\n"
    msg += "=" * 50 + "\n"
    for i, c in enumerate(conflicts, 1):
        msg += f"【{i}】{c['type']}（{c['severity']}）\n"
        msg += f"  详情：{c['detail']}\n"
        msg += f"  建议：{c['suggestion']}\n\n"
    return msg


# ============================================================
# 技能 2：紧急代班
# ============================================================
def handle_emergency_substitution(staff_name: str, date: str, shift_type: str, reason: str = "请假") -> str:
    """当某人无法上班时，快速找到最合适的替代人员"""
    staff_list = load_staff_info("staff_info.xlsx")
    shift_list = load_shift_config("shift_config.xlsx")
    if not staff_list or not shift_list:
        return "数据加载失败，无法进行代班安排"

    # 找到需要代班的员工和班次信息
    target_staff = next((s for s in staff_list if s.name == staff_name), None)
    if not target_staff:
        return f"未找到员工：{staff_name}"

    # 匹配班次类型
    target_shift_type = None
    for st, keywords in SHIFT_KEYWORDS.items():
        if any(kw in shift_type for kw in keywords):
            target_shift_type = st
            break

    # 查找该日期和班次类型的排班（从已生成的排班表）
    try:
        schedule_df = pd.read_excel(os.path.join(DATA_DIR, "schedule_result.xlsx"), engine="openpyxl")
    except FileNotFoundError:
        return "未找到排班表，请先生成排班"

    matching = schedule_df[
        (schedule_df["staff"] == staff_name) &
        (schedule_df["date"] == date) &
        ((target_shift_type is None) | (schedule_df["shift_type"] == target_shift_type))
    ]
    if matching.empty:
        return f"未找到 {staff_name} 在 {date} {shift_type} 的排班记录"

    target_shift = matching.iloc[0]
    shift_info = next((s for s in shift_list if s.shift_id == target_shift["shift_id"]), None)
    required_level = shift_info.required_level if shift_info else 0
    required_dept = shift_info.required_skill if shift_info else ""

    # 寻找替代候选人
    candidates = []
    date_shift_counts = schedule_df[schedule_df["date"] == date].groupby("staff").size().to_dict()
    total_shift_counts = schedule_df.groupby("staff").size().to_dict()

    for staff in staff_list:
        if staff.name == staff_name:
            continue
        if staff.skill_level < required_level:
            continue
        if date not in staff.available_dates:
            continue
        # 部门匹配（护理部除外）
        staff_dept = staff.role.split("-")[0].strip() if "-" in staff.role else staff.role
        if required_dept != "护理部" and required_dept != staff_dept:
            continue
        # 当天已有排班的不考虑
        if date_shift_counts.get(staff.name, 0) > 0:
            continue

        # 评分：技能匹配度 + 当前工作量（工作量少的优先）+ 偏好
        current_workload = total_shift_counts.get(staff.name, 0)
        avg_workload = schedule_df.groupby("staff").size().mean() if len(schedule_df) > 0 else 0
        workload_score = max(0, 10 - current_workload)  # 工作量越少，评分越高

        pref = staff_preferences.get(staff.name)
        pref_bonus = 5 if (pref and date in pref.preferred_dates) else 0

        score = staff.skill_level * 3 + workload_score + pref_bonus
        candidates.append((staff.name, staff.role, staff.skill_level, score))

    if not candidates:
        return f"未找到合适的代班人员。建议：\n1. 放宽技能等级要求\n2. 考虑跨部门调配\n3. 联系临时外聘人员"

    candidates.sort(key=lambda x: -x[3])
    top3 = candidates[:3]

    msg = f"紧急代班安排：{staff_name}（{reason}）\n"
    msg += f"  班次：{date} {target_shift['shift_type']}\n"
    msg += f"  推荐代班人员：\n"
    for i, (name, role, skill, score) in enumerate(top3, 1):
        msg += f"  {i}. {name}（{role}，技能等级{skill}，匹配度：{score:.0f}）\n"
    msg += f"\n建议安排 {top3[0][0]} 代班"
    return msg


# ============================================================
# 技能 3：工作量均衡分析
# ============================================================
def analyze_workload() -> str:
    """分析当前排班的工作量分布情况"""
    try:
        schedule_df = pd.read_excel(os.path.join(DATA_DIR, "schedule_result.xlsx"), engine="openpyxl")
    except FileNotFoundError:
        return "未找到排班结果文件，请先生成排班"

    staff_list = load_staff_info("staff_info.xlsx")

    # 基本统计
    total_shifts = len(schedule_df)
    staff_counts = schedule_df.groupby("staff").size().sort_values(ascending=False)
    avg_shifts = staff_counts.mean()
    std_shifts = staff_counts.std()

    # 班次类型分布
    shift_type_dist = schedule_df["shift_type"].value_counts()

    # 每人班次类型分布
    staff_shift_detail = schedule_df.groupby(["staff", "shift_type"]).size().unstack(fill_value=0)

    # 夜班分布（公平性指标）
    night_counts = schedule_df[schedule_df["shift_type"] == "夜班"].groupby("staff").size()

    # 公平性指标：标准差/均值（变异系数）
    cv = (std_shifts / avg_shifts * 100) if avg_shifts > 0 else 0
    fairness = "优秀" if cv < 15 else ("良好" if cv < 30 else ("一般" if cv < 50 else "较差"))

    msg = f"工作量均衡性分析报告\n"
    msg += "=" * 50 + "\n"
    msg += f"总排班次数：{total_shifts}\n"
    msg += f"参与人数：{len(staff_counts)}\n"
    msg += f"人均班次：{avg_shifts:.1f}\n"
    msg += f"公平性评分：{fairness}（变异系数 {cv:.1f}%）\n\n"

    msg += f"班次类型分布：\n"
    for st, count in shift_type_dist.items():
        bar = "#" * int(count / total_shifts * 30)
        pct = count / total_shifts * 100
        msg += f"  {st}: {count:>3}次 ({pct:.0f}%) {bar}\n"

    msg += f"\n个人工作量排名：\n"
    for i, (name, count) in enumerate(staff_counts.items(), 1):
        diff = count - avg_shifts
        status = f"+{diff:.0f}" if diff > 0 else f"{diff:.0f}"
        bar = "=" * count
        msg += f"  {i:>2}. {name}: {count}次 ({status}) {bar}\n"

    # 夜班公平性
    if not night_counts.empty:
        msg += f"\n夜班分布：\n"
        avg_nights = night_counts.mean()
        for name, count in night_counts.sort_values(ascending=False).items():
            diff = count - avg_nights
            status = f"+{diff:.1f}" if diff > 0 else f"{diff:.1f}"
            msg += f"  {name}: {count}次 (偏差 {status})\n"

    if cv >= 30:
        msg += f"\n改进建议：当前工作量分布{fairness}，建议重新调整排班以提高公平性。"
    return msg


# ============================================================
# 技能 4：排班质量评估
# ============================================================
def evaluate_schedule_quality() -> str:
    """对当前排班表进行全面的质量评估"""
    try:
        schedule_df = pd.read_excel(os.path.join(DATA_DIR, "schedule_result.xlsx"), engine="openpyxl")
    except FileNotFoundError:
        return "未找到排班结果文件，请先生成排班"

    staff_list = load_staff_info("staff_info.xlsx")
    shift_list = load_shift_config("shift_config.xlsx")

    scores: dict[str, list[float]] = {}

    # 1. 覆盖率：所有班次是否都有人
    for shift in shift_list:
        assigned = len(schedule_df[schedule_df["shift_id"] == shift.shift_id])
        coverage = assigned / shift.staff_needed if shift.staff_needed > 0 else 1.0
        scores.setdefault("覆盖率", []).append(coverage)
    avg_coverage = sum(scores["覆盖率"]) / len(scores["覆盖率"]) if scores.get("覆盖率") else 1.0

    # 2. 技能匹配度
    match_count = 0
    for _, row in schedule_df.iterrows():
        staff_info = next((s for s in staff_list if s.name == row["staff"]), None)
        shift_info = next((s for s in shift_list if s.shift_id == row["shift_id"]), None)
        if staff_info and shift_info:
            if staff_info.skill_level >= shift_info.required_level:
                match_count += 1
    skill_match_rate = match_count / len(schedule_df) if len(schedule_df) > 0 else 0

    # 3. 连续工作天数合规率
    violations = 0
    for staff, group in schedule_df.groupby("staff"):
        dates = sorted(pd.to_datetime(group["date"]))
        consecutive = 1
        for i in range(1, len(dates)):
            if (dates[i] - dates[i - 1]).days == 1:
                consecutive += 1
                if consecutive > MAX_CONSECUTIVE_SHIFTS:
                    violations += 1
            else:
                consecutive = 1
    compliance_rate = 1 - (violations / len(schedule_df)) if len(schedule_df) > 0 else 1.0

    # 4. 工作量均衡性
    staff_counts = schedule_df.groupby("staff").size()
    avg_shifts = staff_counts.mean()
    std_shifts = staff_counts.std()
    cv = (std_shifts / avg_shifts * 100) if avg_shifts > 0 else 0
    balance_score = max(0, 100 - cv * 2)

    # 5. 综合评分
    total_score = (
        avg_coverage * 25 +
        skill_match_rate * 25 +
        compliance_rate * 25 +
        (balance_score / 100) * 25
    )

    grade = "A" if total_score >= 90 else ("B" if total_score >= 75 else ("C" if total_score >= 60 else "D"))

    msg = f"排班质量评估报告\n"
    msg += "=" * 50 + "\n"
    msg += f"综合评分：{total_score:.1f}/100（等级：{grade}）\n\n"
    msg += f"细分指标：\n"
    msg += f"  1. 覆盖率：{avg_coverage*100:.1f}%（满分25分，得分：{avg_coverage*25:.1f}）\n"
    msg += f"  2. 技能匹配度：{skill_match_rate*100:.1f}%（满分25分，得分：{skill_match_rate*25:.1f}）\n"
    msg += f"  3. 连续性合规：{compliance_rate*100:.1f}%（满分25分，得分：{compliance_rate*25:.1f}）\n"
    msg += f"  4. 均衡性：{balance_score:.0f}/100（满分25分，得分：{balance_score*0.25:.1f}）\n"

    # 改进建议
    suggestions = []
    if avg_coverage < 1.0:
        suggestions.append("存在班次未满编情况，建议增加可用人员或调整需求")
    if skill_match_rate < 1.0:
        suggestions.append(f"有 {int((1-skill_match_rate)*100)}% 的排班技能不匹配，需调整人员安排")
    if violations > 0:
        suggestions.append(f"存在 {violations} 处连续排班违规，需重新分配")
    if cv >= 30:
        suggestions.append("工作量分布不均，建议平衡各员工班次数")
    if not suggestions:
        suggestions.append("各项指标良好，排班质量优秀！")

    msg += f"\n改进建议：\n"
    for i, s in enumerate(suggestions, 1):
        msg += f"  {i}. {s}\n"
    return msg


# ============================================================
# 技能 5：偏好学习与记录
# ============================================================
def learn_preference(user_input: str) -> str:
    """从用户输入中学习并记录排班偏好"""
    prompt = PREFERENCE_EXTRACT_PROMPT.format(user_input=user_input)
    try:
        response = chat(prompt)
        result = json.loads(response)
        logger.info(f"偏好学习结果: {result}")

        staff_name = result.get("staff_name")
        if not staff_name:
            return "未能识别员工姓名，请使用明确的员工名称来表达偏好"

        # 获取或创建偏好记录
        if staff_name not in staff_preferences:
            staff_preferences[staff_name] = StaffPreference(staff_name=staff_name)

        pref = staff_preferences[staff_name]
        changes = []

        if result.get("preferred_dates"):
            for d in result["preferred_dates"]:
                if d not in pref.preferred_dates:
                    pref.preferred_dates.append(d)
            changes.append(f"偏好日期: {', '.join(result['preferred_dates'])}")

        if result.get("avoided_dates"):
            for d in result["avoided_dates"]:
                if d not in pref.avoided_dates:
                    pref.avoided_dates.append(d)
            changes.append(f"避免日期: {', '.join(result['avoided_dates'])}")

        if result.get("preferred_shifts"):
            for s in result["preferred_shifts"]:
                if s not in pref.preferred_shifts:
                    pref.preferred_shifts.append(s)
            changes.append(f"偏好班次: {', '.join(result['preferred_shifts'])}")

        if changes:
            msg = f"已记录 {staff_name} 的排班偏好：\n"
            for c in changes:
                msg += f"  - {c}\n"
            msg += f"系统将在下次排班时参考这些偏好。"
        else:
            msg = f"已更新 {staff_name} 的偏好记录。"

        return msg
    except (json.JSONDecodeError, RuntimeError) as e:
        logger.error(f"偏好学习失败: {e}")
        return "偏好学习暂时不可用，请稍后再试"


def get_preference_report() -> str:
    """获取所有已记录的偏好信息"""
    if not staff_preferences:
        return "当前未记录任何排班偏好。您可以通过自然语言告诉系统您的偏好，例如：\n  - '李医生希望周一和周三上早班'\n  - '王护士周五晚上不想上班'"

    msg = "已记录的排班偏好：\n"
    msg += "=" * 50 + "\n"
    for name, pref in staff_preferences.items():
        msg += f"\n【{name}】\n"
        if pref.preferred_dates:
            msg += f"  偏好日期：{', '.join(pref.preferred_dates)}\n"
        if pref.avoided_dates:
            msg += f"  避免日期：{', '.join(pref.avoided_dates)}\n"
        if pref.preferred_shifts:
            msg += f"  偏好班次：{', '.join(pref.preferred_shifts)}\n"
    return msg
