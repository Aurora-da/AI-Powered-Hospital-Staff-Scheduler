import json
from llm_client import chat
from config import logger


class IntentResult:
    """意图识别结果封装"""
    def __init__(self, intent_type, staff_name=None, date=None, shift_type=None, target_staff=None, reason=None):
        self.intent_type = intent_type  # 扩展：generate_schedule/swap_shift/query_schedule/conflict_detect/emergency_substitute/workload_analysis/quality_evaluate/learn_preference/show_preference/general_chat/unsupported
        self.staff_name = staff_name
        self.date = date
        self.shift_type = shift_type
        self.target_staff = target_staff
        self.reason = reason  # 紧急代班的原因（如"请假"、"生病"）


def detect_intent(user_input: str) -> IntentResult:
    """检测用户输入的意图"""
    prompt = f"""
    分析以下用户输入，识别其意图，并输出JSON格式结果：
    用户输入：{user_input}

    意图类型（intent_type）可选值：
    - generate_schedule: 生成排班表，与医院员工排班表生成相关的需求
    - swap_shift: 调班，与医院员工班次调换相关的需求
    - query_schedule: 查询排班，与医院员工排班信息查询相关的需求
    - conflict_detect: 冲突检测，检查排班表是否有冲突、违规、不均衡等问题
    - emergency_substitute: 紧急代班，某人无法上班需要找人替代（如请假、生病、临时有事）
    - workload_analysis: 工作量分析，分析排班工作量分布、公平性等
    - quality_evaluate: 质量评估，评估排班表整体质量并打分
    - learn_preference: 学习偏好，记录员工对排班的偏好（日期、班次等喜好或避免）
    - show_preference: 查看偏好，查看已记录的员工排班偏好
    - general_chat: 通用对话，日常闲聊、咨询排班相关知识、非工具类的问答需求
    - unsupported: 不支持的功能，查天气、查路线、订酒店等本系统未实现的工具类需求

    输出字段：
    - intent_type: 意图类型（必须是上述可选值）
    - staff_name: 员工姓名（swap_shift/query_schedule/emergency_substitute/learn_preference时必填，其他意图填null）
    - date: 日期（格式YYYY-MM-DD，swap_shift/query_schedule/emergency_substitute时必填，其他意图填null）
    - shift_type: 班次类型（早班/中班/夜班，swap_shift/query_schedule/emergency_substitute时必填，其他意图填null）
    - target_staff: 目标调班员工（仅swap_shift时可选，其他意图填null）
    - reason: 原因说明（仅emergency_substitute时可选，如"请假"、"生病"等，其他意图填null）

    仅输出JSON，不要添加其他内容，null用英文小写。
    """

    try:
        response = chat(prompt)
        result = json.loads(response)
        logger.info(f"意图识别结果: {result}")

        return IntentResult(
            intent_type=result.get("intent_type"),
            staff_name=result.get("staff_name"),
            date=result.get("date"),
            shift_type=result.get("shift_type"),
            target_staff=result.get("target_staff"),
            reason=result.get("reason")
        )
    except json.JSONDecodeError as e:
        logger.error(f"LLM返回非JSON格式: {response}, 错误: {e}")
        raise ValueError("意图识别失败，请重新输入")
    except Exception as e:
        logger.error(f"意图识别异常: {e}", exc_info=True)
        raise
