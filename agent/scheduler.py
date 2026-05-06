import pandas as pd
from ortools.sat.python import cp_model
from excel_loader import StaffInfo, ShiftConfig
from config import MAX_CONSECUTIVE_SHIFTS, logger


def check_conflicts(df: pd.DataFrame) -> list[str]:
    conflicts = []
    df_sorted = df.sort_values(by=["staff", "date"])

    for staff, group in df_sorted.groupby("staff"):
        dates = pd.to_datetime(group["date"]).sort_values()
        consecutive = 1
        for i in range(1, len(dates)):
            if (dates.iloc[i] - dates.iloc[i - 1]).days == 1:
                consecutive += 1
                if consecutive > MAX_CONSECUTIVE_SHIFTS:
                    conflicts.append(
                        f"{staff} 连续排班 {consecutive} 天 ({dates.iloc[i - 1 - MAX_CONSECUTIVE_SHIFTS + 1].strftime('%Y-%m-%d')} 至 {dates.iloc[i].strftime('%Y-%m-%d')})"
                    )
            else:
                consecutive = 1
    return conflicts


def solve_schedule(staff_list: list[StaffInfo], shift_list: list[ShiftConfig]) -> pd.DataFrame:
    if not staff_list or not shift_list:
        raise ValueError("员工或班次数据为空，无法排班")

    model = cp_model.CpModel()

    # 变量：staff_shift[(staff_id, shift_id)] 是否分配
    staff_shift = {}
    for staff in staff_list:
        for shift in shift_list:
            staff_shift[(staff.staff_id, shift.shift_id)] = model.NewBoolVar(f"{staff.staff_id}_{shift.shift_id}")

    # 约束1：每个班次正好满足所需人数
    for shift in shift_list:
        assigned = [staff_shift[(s.staff_id, shift.shift_id)] for s in staff_list]
        model.Add(sum(assigned) == shift.staff_needed)

    # 约束2：技能等级足够 + 部门匹配（核心改进）
    for staff in staff_list:
        dept = staff.role.split('-')[0].strip() if '-' in staff.role else staff.role
        for shift in shift_list:
            req_dept = shift.required_skill
            if (staff.skill_level < shift.required_level or
                    (req_dept != "护理部" and dept != "护理部" and req_dept != dept)):
                model.Add(staff_shift[(staff.staff_id, shift.shift_id)] == 0)

    # 约束3：不超过最大排班数
    for staff in staff_list:
        assigned_shifts = [staff_shift[(staff.staff_id, sh.shift_id)] for sh in shift_list]
        model.Add(sum(assigned_shifts) <= staff.max_shifts)

    # 约束4：只在可用日期排班
    for staff in staff_list:
        if not staff.available_dates:
            continue
        avail_set = set(staff.available_dates)
        for shift in shift_list:
            if shift.date not in avail_set:
                model.Add(staff_shift[(staff.staff_id, shift.shift_id)] == 0)

    # 约束5：连续工作天数不超过 MAX_CONSECUTIVE_SHIFTS
    for staff in staff_list:
        date_to_vars = {}
        for shift in shift_list:
            date_to_vars.setdefault(shift.date, []).append(staff_shift[(staff.staff_id, shift.shift_id)])

        sorted_dates = sorted(date_to_vars.keys())
        worked_on_date = {}
        for d in sorted_dates:
            worked = model.NewBoolVar(f'{staff.staff_id}_worked_{d}')
            shift_sum = sum(date_to_vars[d])
            model.Add(shift_sum >= 1).OnlyEnforceIf(worked)
            model.Add(shift_sum == 0).OnlyEnforceIf(worked.Not())
            worked_on_date[d] = worked

        for i in range(len(sorted_dates) - MAX_CONSECUTIVE_SHIFTS):
            window_sum = sum(worked_on_date[sorted_dates[i + j]] for j in range(MAX_CONSECUTIVE_SHIFTS + 1))
            model.Add(window_sum <= MAX_CONSECUTIVE_SHIFTS)

    # 求解
    solver = cp_model.CpSolver()
    # 可选：设置求解时间上限（秒）
    solver.parameters.max_time_in_seconds = 60.0
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"排班无解（状态: {status}）")

    # 收集结果
    rows = []
    staff_name_map = {s.staff_id: s.name for s in staff_list}
    role_map = {s.staff_id: s.role for s in staff_list}
    skill_map = {s.staff_id: s.skill_level for s in staff_list}

    for shift in shift_list:
        for staff in staff_list:
            if solver.Value(staff_shift[(staff.staff_id, shift.shift_id)]) == 1:
                rows.append({
                    "staff_id": staff.staff_id,
                    "staff": staff_name_map[staff.staff_id],
                    "shift_id": shift.shift_id,
                    "date": shift.date,
                    "shift_type": shift.shift_type,
                    "role": role_map[staff.staff_id],
                    "skill_level": skill_map[staff.staff_id]
                })

    df_result = pd.DataFrame(rows)

    # 冲突检查（日志）
    conflicts = check_conflicts(df_result)
    if conflicts:
        logger.warning("存在连续排班冲突（尽管已加约束，仍可能因数据原因出现）：")
        for c in conflicts:
            logger.warning(f"  - {c}")

    return df_result