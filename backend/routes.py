import pandas as pd
from fastapi import APIRouter, HTTPException, Request

from backend.schemas import (
    LoginRequest, SwapRequest, QueryRequest, EmergencySubstituteRequest,
    LearnPreferenceRequest, ChatRequest,
)
from backend.auth import login_user, get_current_user, require_role, init_users
from excel_loader import load_staff_info, load_shift_config
from excel_exporter import export_schedule, export_history, export_swap_result
from scheduler import solve_schedule
from swap_solver import solve_swap
from agent import detect_intent
from chat_tools import general_chat_handler, add_memory
from skills import (
    detect_conflicts,
    handle_emergency_substitution,
    analyze_workload,
    evaluate_schedule_quality,
    learn_preference,
    get_preference_report,
)
from config import logger, SHIFT_KEYWORDS

router = APIRouter(prefix="/api")

# 启动时初始化用户密码哈希
init_users()


# ===== Auth =====

@router.post("/auth/login")
def login(req: LoginRequest):
    if not req.username or not req.password:
        raise HTTPException(400, "用户名和密码不能为空")
    result = login_user(req.username, req.password)
    if not result:
        raise HTTPException(401, "用户名或密码错误")
    return {"success": True, **result}


@router.get("/auth/me")
def me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "未登录或登录已过期")
    return {"success": True, **user}


def _load_data():
    staff = load_staff_info("staff_info.xlsx")
    shifts = load_shift_config("shift_config.xlsx")
    return staff, shifts


def _find_original_shift(shifts, date: str, shift_text: str):
    if not date or not shift_text:
        return None
    target_shift_type = None
    for shift_type, keywords in SHIFT_KEYWORDS.items():
        if any(keyword in shift_text for keyword in keywords):
            target_shift_type = shift_type
            break
    for shift in shifts:
        if shift.date == date and (target_shift_type is None or shift.shift_type == target_shift_type):
            return shift
    return None


# ===== Staff & Shifts =====

@router.get("/staff")
def get_staff():
    staff, _ = _load_data()
    return [
        {
            "staff_id": s.staff_id,
            "name": s.name,
            "role": s.role,
            "skill_level": s.skill_level,
            "max_shifts": s.max_shifts,
            "available_dates": s.available_dates,
        }
        for s in staff
    ]


@router.get("/shifts")
def get_shifts():
    _, shifts = _load_data()
    return [
        {
            "shift_id": s.shift_id,
            "date": s.date,
            "shift_type": s.shift_type,
            "required_skill": s.required_skill,
            "required_level": s.required_level,
            "staff_needed": s.staff_needed,
        }
        for s in shifts
    ]


# ===== Schedule =====

@router.get("/schedule")
def get_schedule(request: Request = None):
    """获取当前排班结果（员工仅看自己）"""
    from config import DATA_DIR
    import os
    path = os.path.join(DATA_DIR, "schedule_result.xlsx")
    try:
        df = pd.read_excel(path, engine="openpyxl")
        user = get_current_user(request) if request else None
        if user and user["role"] == "staff" and "staff" in df.columns:
            df = df[df["staff"] == user["name"]]
        return df.to_dict(orient="records")
    except FileNotFoundError:
        return []


@router.post("/schedule/generate")
def generate_schedule(request: Request, _current_user: dict = None):
    user = get_current_user(request)
    if not user or user["role"] != "manager":
        raise HTTPException(403, "权限不足：仅管理层可生成排班")
    staff, shifts = _load_data()
    if not staff or not shifts:
        raise HTTPException(status_code=400, detail="员工或班次数据为空")
    try:
        schedule_df = solve_schedule(staff, shifts)
        export_schedule(schedule_df)
        name_to_id = {s.name: s.staff_id for s in staff}
        schedule_df["staff_id"] = schedule_df["staff"].map(name_to_id)
        export_history(schedule_df[["staff_id", "date", "shift_id"]])
        return {"success": True, "data": schedule_df.to_dict(orient="records")}
    except Exception as e:
        logger.error(f"生成排班失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule/swap")
def swap_shift(req: SwapRequest, request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "manager":
        raise HTTPException(403, "权限不足：仅管理层可调班")
    staff, shifts = _load_data()
    if not staff or not shifts:
        raise HTTPException(status_code=400, detail="员工或班次数据为空")
    original_shift = _find_original_shift(shifts, req.date, req.shift_type)
    if not original_shift:
        raise HTTPException(status_code=404, detail=f"未找到 {req.date} {req.shift_type} 的班次")
    try:
        swap_df, logs = solve_swap(staff, shifts, original_shift, req.target_staff)
        export_swap_result(swap_df)
        return {"success": True, "logs": logs, "data": swap_df.to_dict(orient="records")}
    except Exception as e:
        logger.error(f"调班失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule/query")
def query_schedule(req: QueryRequest, request: Request = None):
    from config import DATA_DIR
    import os
    path = os.path.join(DATA_DIR, "schedule_result.xlsx")
    try:
        schedule_df = pd.read_excel(path, engine="openpyxl")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到排班结果文件，请先生成排班")
    user = get_current_user(request) if request else None
    if user and user["role"] == "staff":
        req.staff_name = user["name"]  # 员工只能搜自己
    filter_cond = pd.Series([True] * len(schedule_df))
    if req.staff_name:
        filter_cond &= schedule_df["staff"] == req.staff_name
    if req.date:
        filter_cond &= schedule_df["date"] == req.date
    if req.shift_type:
        filter_cond &= schedule_df["shift_type"] == req.shift_type
    result = schedule_df[filter_cond]
    return {"success": True, "data": result.to_dict(orient="records")}


# ===== Conflicts =====

@router.get("/conflicts")
def get_conflicts():
    result = detect_conflicts()
    return {"success": True, "report": result}


# ===== Emergency Substitute =====

@router.post("/emergency/substitute")
def emergency_substitute(req: EmergencySubstituteRequest, request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "manager":
        raise HTTPException(403, "权限不足：仅管理层可处理紧急代班")
    result = handle_emergency_substitution(req.staff_name, req.date, req.shift_type, req.reason)
    return {"success": True, "report": result}


# ===== Workload =====

@router.get("/workload")
def get_workload():
    result = analyze_workload()
    return {"success": True, "report": result}


# ===== Quality =====

@router.get("/quality")
def get_quality():
    result = evaluate_schedule_quality()
    return {"success": True, "report": result}


# ===== Preferences =====

@router.get("/preferences")
def get_preferences():
    result = get_preference_report()
    return {"success": True, "report": result}


@router.post("/preferences/learn")
def learn_preferences(req: LearnPreferenceRequest, request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "manager":
        raise HTTPException(403, "权限不足：仅管理层可管理偏好")
    result = learn_preference(req.user_input)
    return {"success": True, "report": result}


# ===== Chat =====

@router.post("/chat")
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    try:
        intent = detect_intent(req.message)
        if intent.intent_type == "general_chat":
            response = general_chat_handler(req.message)
        elif intent.intent_type == "generate_schedule":
            staff, shifts = _load_data()
            if not staff or not shifts:
                response = "生成排班失败：员工或班次数据为空"
            else:
                try:
                    schedule_df = solve_schedule(staff, shifts)
                    export_schedule(schedule_df)
                    name_to_id = {s.name: s.staff_id for s in staff}
                    schedule_df["staff_id"] = schedule_df["staff"].map(name_to_id)
                    export_history(schedule_df[["staff_id", "date", "shift_id"]])
                    response = "排班生成成功！\n" + schedule_df[["staff", "date", "shift_type"]].head(10).to_string(index=False)
                except Exception as e:
                    response = f"生成排班失败: {str(e)}"
        elif intent.intent_type == "swap_shift":
            staff, shifts = _load_data()
            if not staff or not shifts:
                response = "调班失败：员工或班次数据为空"
            else:
                original_shift = _find_original_shift(shifts, intent.date, intent.shift_type)
                if not original_shift:
                    response = f"调班失败：未找到 {intent.date} {intent.shift_type} 的班次"
                else:
                    try:
                        swap_df, logs = solve_swap(staff, shifts, original_shift, intent.target_staff)
                        export_swap_result(swap_df)
                        response = "调班成功！\n" + "\n".join(f"- {log}" for log in logs)
                    except Exception as e:
                        response = f"调班失败: {str(e)}"
        elif intent.intent_type == "query_schedule":
            from config import DATA_DIR
            import os
            path = os.path.join(DATA_DIR, "schedule_result.xlsx")
            try:
                schedule_df = pd.read_excel(path, engine="openpyxl")
                filter_cond = pd.Series([True] * len(schedule_df))
                if intent.staff_name:
                    filter_cond &= schedule_df["staff"] == intent.staff_name
                if intent.date:
                    filter_cond &= schedule_df["date"] == intent.date
                if intent.shift_type:
                    filter_cond &= schedule_df["shift_type"] == intent.shift_type
                result_df = schedule_df[filter_cond]
                if result_df.empty:
                    response = "未找到匹配的排班信息"
                else:
                    response = "查询结果：\n" + result_df[["staff", "date", "shift_type", "role"]].to_string(index=False)
            except FileNotFoundError:
                response = "查询失败：未找到排班结果文件，请先生成排班"
        elif intent.intent_type == "conflict_detect":
            response = detect_conflicts()
        elif intent.intent_type == "emergency_substitute":
            if not intent.staff_name or not intent.date or not intent.shift_type:
                response = "紧急代班需要提供：员工姓名、日期和班次类型"
            else:
                response = handle_emergency_substitution(intent.staff_name, intent.date, intent.shift_type, intent.reason or "临时有事")
        elif intent.intent_type == "workload_analysis":
            response = analyze_workload()
        elif intent.intent_type == "quality_evaluate":
            response = evaluate_schedule_quality()
        elif intent.intent_type == "learn_preference":
            response = learn_preference(req.message)
        elif intent.intent_type == "show_preference":
            response = get_preference_report()
        else:
            response = "暂不支持该功能。我是医院智能排班与调班助手，可提供排班生成、调班、查询、冲突检测、紧急代班、工作量分析、质量评估、偏好管理等功能～"
        add_memory(req.message, response)
        return {"success": True, "response": response}
    except Exception as e:
        logger.error(f"聊天处理失败: {e}", exc_info=True)
        return {"success": False, "response": f"处理请求失败: {str(e)}"}
