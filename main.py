import pandas as pd
from config import logger, SHIFT_KEYWORDS
from excel_loader import load_staff_info, load_shift_config, StaffInfo, ShiftConfig
from excel_exporter import export_schedule, export_history, export_swap_result
from scheduler import solve_schedule
from swap_solver import solve_swap
from agent import detect_intent
# 新增：导入通用对话工具
from chat_tools import general_chat_handler, add_memory
# 新增：导入智能技能模块
from skills import (
    detect_conflicts,
    handle_emergency_substitution as do_emergency_substitution,
    analyze_workload,
    evaluate_schedule_quality,
    learn_preference,
    get_preference_report,
)


def load_data() -> tuple[list[StaffInfo], list[ShiftConfig]]:
    """加载员工和班次数据"""
    try:
        staff = load_staff_info("staff_info.xlsx")
        shifts = load_shift_config("shift_config.xlsx")
        logger.info(f"成功加载 {len(staff)} 名员工，{len(shifts)} 个班次")
        return staff, shifts
    except Exception as e:
        logger.error(f"数据加载失败: {e}", exc_info=True)
        return [], []


def _find_original_shift(shifts: list[ShiftConfig], date: str, shift_text: str) -> ShiftConfig:
    """根据日期和班次描述查找匹配的班次"""
    if not date or not shift_text:
        logger.warning("日期或班次描述为空，无法查找班次")
        return None
    # 匹配班次关键词
    target_shift_type = None
    for shift_type, keywords in SHIFT_KEYWORDS.items():
        if any(keyword in shift_text for keyword in keywords):
            target_shift_type = shift_type
            break
    # 查找匹配的班次
    for shift in shifts:
        if shift.date == date and (target_shift_type is None or shift.shift_type == target_shift_type):
            logger.info(f"找到匹配班次: {shift.shift_id} ({shift.date} {shift.shift_type})")
            return shift
    logger.warning(f"未找到匹配班次: 日期={date}, 班次描述={shift_text}")
    return None


def handle_generate_schedule():
    """处理生成排班请求"""
    staff, shifts = load_data()
    if not staff or not shifts:
        logger.error("生成排班失败：员工或班次数据为空")
        return "生成排班失败：员工或班次数据为空"
    try:
        schedule_df = solve_schedule(staff, shifts)
        export_schedule(schedule_df)

        # 补充staff_id并导出历史
        name_to_id = {s.name: s.staff_id for s in staff}
        schedule_df["staff_id"] = schedule_df["staff"].map(name_to_id)
        export_history(schedule_df[["staff_id", "date", "shift_id"]])

        msg = "排班生成成功！结果已保存到 data/schedule_result.xlsx\n"
        msg += "排班预览：\n"
        msg += schedule_df[["staff", "date", "shift_type"]].head(10).to_string(index=False)
        return msg
    except Exception as e:
        logger.error(f"生成排班失败: {e}", exc_info=True)
        return f"生成排班失败: {str(e)}"


def handle_swap_shift(intent_result):
    """处理调班请求"""
    staff, shifts = load_data()
    if not staff or not shifts:
        logger.error("调班失败：员工或班次数据为空")
        return "调班失败：员工或班次数据为空"
    # 查找原班次
    original_shift = _find_original_shift(shifts, intent_result.date, intent_result.shift_type)
    if not original_shift:
        return f"调班失败：未找到 {intent_result.date} {intent_result.shift_type} 的班次"
    try:
        swap_df, logs = solve_swap(
            staff, shifts, original_shift, intent_result.target_staff
        )
        export_swap_result(swap_df)

        msg = "调班成功！\n"
        for log in logs:
            msg += f"- {log}\n"
        msg += "调班详情已保存到 data/swap_history.xlsx"
        return msg.strip()
    except Exception as e:
        logger.error(f"调班失败: {e}", exc_info=True)
        return f"调班失败: {str(e)}"


def handle_query_schedule(intent_result):
    """处理查询排班请求"""
    staff, shifts = load_data()
    if not staff or not shifts:
        logger.error("查询排班失败：员工或班次数据为空")
        return "查询排班失败：员工或班次数据为空"
    # 读取排班结果
    try:
        schedule_df = pd.read_excel("data/schedule_result.xlsx", engine="openpyxl")
    except FileNotFoundError:
        return "查询失败：未找到排班结果文件，请先生成排班"
    # 筛选查询结果
    filter_cond = pd.Series([True] * len(schedule_df))
    if intent_result.staff_name:
        filter_cond &= schedule_df["staff"] == intent_result.staff_name
    if intent_result.date:
        filter_cond &= schedule_df["date"] == intent_result.date
    if intent_result.shift_type:
        filter_cond &= schedule_df["shift_type"] == intent_result.shift_type
    result_df = schedule_df[filter_cond]
    if result_df.empty:
        return "未找到匹配的排班信息"
    else:
        msg = "查询结果：\n"
        msg += result_df[["staff", "date", "shift_type", "role"]].to_string(index=False)
        return msg


# ========== 新增智能技能处理函数 ==========

def handle_conflict_detect():
    """处理冲突检测请求"""
    res = detect_conflicts()
    return res


def handle_emergency_substitute(intent_result):
    """处理紧急代班请求"""
    if not intent_result.staff_name or not intent_result.date or not intent_result.shift_type:
        return "紧急代班需要提供：员工姓名、日期和班次类型。例如：'张医生明天夜班请假了，找人代班'"
    reason = intent_result.reason or "临时有事"
    res = do_emergency_substitution(
        intent_result.staff_name,
        intent_result.date,
        intent_result.shift_type,
        reason
    )
    return res


def handle_workload_analysis():
    """处理工作量分析请求"""
    res = analyze_workload()
    return res


def handle_quality_evaluate():
    """处理质量评估请求"""
    res = evaluate_schedule_quality()
    return res


def handle_learn_preference(user_input):
    """处理偏好学习请求"""
    res = learn_preference(user_input)
    return res


def handle_show_preference():
    """处理查看偏好请求"""
    res = get_preference_report()
    return res


# 新增：处理不支持的功能
def handle_unsupported(user_input):
    """处理不支持的功能请求"""
    msg = f"目前暂不支持「{user_input}」相关功能，我是医院智能排班与调班智能体，可为你提供排班生成、调班、排班查询、冲突检测、紧急代班、工作量分析、质量评估、偏好管理等服务～"
    # 添加到记忆
    add_memory(user_input, msg)
    return msg


def main():
    """主交互逻辑"""
    print("=" * 50)
    print("      医院智能排班与调班智能体（智能版）")
    print("=" * 50)
    print("支持的功能：")
    print("1. 排班管理：生成排班表、调班、查询排班")
    print("2. 智能技能：")
    print("   - 冲突检测：自动发现排班冲突和违规")
    print("   - 紧急代班：快速找到合适的替代人员")
    print("   - 工作量分析：分析排班公平性和分布")
    print("   - 质量评估：给排班表打分并给建议")
    print("   - 偏好管理：学习并记住员工排班偏好")
    print("3. 通用对话：日常闲聊、排班知识咨询")
    print("4. 记忆功能：自动记录历史对话上下文")
    print("示例指令：")
    print("  - 生成排班表")
    print("  - 张医生2024-10-03夜班想调班")
    print("  - 查询李护士2024-10-01的排班")
    print("  - 检测当前排班有没有冲突")
    print("  - 张医生明天夜班生病了，找人代班")
    print("  - 分析一下大家的工作量是否均衡")
    print("  - 评估当前排班表的质量")
    print("  - 李医生希望周一和周三上早班")
    print("  - 查看所有员工的偏好记录")
    print("输入 '退出' 结束程序")
    print("=" * 50)
    while True:
        user_input = input("\n请输入您的需求：").strip()
        if user_input.lower() in ["退出", "exit", "quit"]:
            print("程序已退出，感谢使用！")
            break
        if not user_input:
            print("输入不能为空，请重新输入")
            continue
        try:
            # 意图识别
            intent_result = detect_intent(user_input)

            # 处理不同意图
            if intent_result.intent_type == "generate_schedule":
                res = handle_generate_schedule()
                add_memory(user_input, res)
                print(res)
            elif intent_result.intent_type == "swap_shift":
                res = handle_swap_shift(intent_result)
                add_memory(user_input, res)
                print(res)
            elif intent_result.intent_type == "query_schedule":
                res = handle_query_schedule(intent_result)
                add_memory(user_input, res)
                print(res)
            elif intent_result.intent_type == "conflict_detect":
                res = handle_conflict_detect()
                add_memory(user_input, res)
                print(res)
            elif intent_result.intent_type == "emergency_substitute":
                res = handle_emergency_substitute(intent_result)
                add_memory(user_input, res)
                print(res)
            elif intent_result.intent_type == "workload_analysis":
                res = handle_workload_analysis()
                add_memory(user_input, res)
                print(res)
            elif intent_result.intent_type == "quality_evaluate":
                res = handle_quality_evaluate()
                add_memory(user_input, res)
                print(res)
            elif intent_result.intent_type == "learn_preference":
                res = handle_learn_preference(user_input)
                add_memory(user_input, res)
                print(res)
            elif intent_result.intent_type == "show_preference":
                res = handle_show_preference()
                add_memory(user_input, res)
                print(res)
            elif intent_result.intent_type == "general_chat":
                # 通用对话（自带记忆处理）
                res = general_chat_handler(user_input)
                print(res)
            elif intent_result.intent_type == "unsupported":
                # 不支持的功能
                res = handle_unsupported(user_input)
                print(res)
            else:
                res = f"暂不支持该意图：{intent_result.intent_type}"
                add_memory(user_input, res)
                print(res)
        except Exception as e:
            logger.error(f"处理请求失败: {e}", exc_info=True)
            error_msg = f"处理请求失败: {str(e)}"
            add_memory(user_input, error_msg)
            print(error_msg)


if __name__ == "__main__":
    main()
