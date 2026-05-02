import pandas as pd
from ortools.sat.python import cp_model
from excel_loader import StaffInfo, ShiftConfig
from config import logger


def solve_swap(
    staff_list: list[StaffInfo],
    shift_list: list[ShiftConfig],
    original_shift: ShiftConfig,
    target_staff_name: str = None
) -> tuple[pd.DataFrame, list[str]]:
    """求解调班问题"""
    # 1. 准备数据
    staff_name_map = {s.name: s for s in staff_list}
    shift_id_map = {sh.shift_id: sh for sh in shift_list}
    
    # 2. 找到原排班中安排在该班次的员工
    original_staff = None
    # 这里需要从历史排班表中读取，简化版先随机选一个符合条件的员工
    for staff in staff_list:
        if original_shift.date in staff.available_dates and staff.skill_level >= original_shift.required_level:
            original_staff = staff
            break
    
    if not original_staff:
        raise ValueError(f"未找到可安排在{original_shift.date} {original_shift.shift_type}的员工")
    
    # 3. 找到目标调班员工（如果指定）
    target_staff = staff_name_map.get(target_staff_name) if target_staff_name else None
    
    # 4. 构建调班模型
    model = cp_model.CpModel()
    swap_vars = {}
    
    # 候选员工（排除原员工，需满足技能要求）
    candidates = [s for s in staff_list
                  if s.staff_id != original_staff.staff_id
                  and s.skill_level >= original_shift.required_level]
    if target_staff and target_staff in candidates:
        candidates = [target_staff]  # 优先目标员工

    if not candidates:
        raise ValueError("未找到满足技能要求的候选员工")

    for staff in candidates:
        swap_vars[staff.staff_id] = model.NewBoolVar(f"swap_{staff.staff_id}")

    model.Add(sum(swap_vars.values()) == 1)
    
    # 5. 求解
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
        raise RuntimeError("未找到可行的调班方案")
    
    # 6. 构建结果
    swap_staff_id = None
    for staff_id, var in swap_vars.items():
        if solver.Value(var) == 1:
            swap_staff_id = staff_id
            break
    
    swap_staff = next(s for s in staff_list if s.staff_id == swap_staff_id)
    logger.info(f"调班结果：{original_staff.name} ↔ {swap_staff.name} ({original_shift.date} {original_shift.shift_type})")
    
    # 构建调班结果表
    result_df = pd.DataFrame([{
        "original_staff": original_staff.name,
        "swap_staff": swap_staff.name,
        "shift_date": original_shift.date,
        "shift_type": original_shift.shift_type,
        "shift_id": original_shift.shift_id,
        "swap_time": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    }])
    
    # 调班日志
    logs = [
        f"调班成功：{original_staff.name} 的 {original_shift.date} {original_shift.shift_type} 班次调整为 {swap_staff.name} 负责",
        f"调班时间：{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ]
    
    return result_df, logs