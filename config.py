import os
import logging
from dotenv import load_dotenv

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# API配置
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
MODEL_NAME = os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen3-Next-80B-A3B-Instruct")
API_URL = "https://api.siliconflow.cn/v1/chat/completions"

# 路径配置
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    logger.info(f"创建数据目录: {DATA_DIR}")

# 业务配置
SHIFT_KEYWORDS = {
    "早班": ["早", "白"],
    "中班": ["中"],
    "夜班": ["晚", "夜"]
}
MAX_CONSECUTIVE_SHIFTS = 2  # 最大连续排班天数
LLM_MAX_RETRIES = 3         # LLM调用最大重试次数
EXCEL_ENGINE = "openpyxl"   # Excel读写引擎

# 优化后：对话记忆配置（增加近期权重）
MAX_MEMORY_LENGTH = 10      # 最大记忆对话条数（用户+AI为1条）
RECENT_MEMORY_NUM = 2       # 近期对话条数（高权重），建议2-3条

# 智能技能配置
WORKLOAD_FAIRNESS_EXCELLENT = 15   # 变异系数 < 15% 为优秀
WORKLOAD_FAIRNESS_GOOD = 30        # 变异系数 < 30% 为良好
WORKLOAD_FAIRNESS_AVERAGE = 50     # 变异系数 < 50% 为一般
MAX_NIGHT_SHIFTS_PER_PERSON = 3    # 每人最大夜班次数

# 偏好学习 Prompt 模板
PREFERENCE_EXTRACT_PROMPT = """
从以下用户输入中提取排班偏好信息，输出JSON格式：
用户输入：{user_input}

提取以下信息（如无法提取则填null）：
- staff_name: 员工姓名
- preferred_dates: 偏好上班的日期列表（如["2024-10-01", "2024-10-05"]）
- avoided_dates: 不希望上班的日期列表
- preferred_shifts: 偏好的班次类型（如["早班", "中班"]）
- preference_type: 偏好类型（"preferred"表示偏好/"avoided"表示避免）

仅输出JSON，不要添加其他内容。
"""
# 优化后的记忆Prompt模板，明确权重规则
MEMORY_PROMPT_TPL = """
# 对话上下文参考规则
1. 【最近对话】为高优先级，优先基于此回复用户；【历史对话】为低优先级，仅做补充参考
2. 若上下文无相关信息，直接回复用户最新问题即可，无需强行关联
3. 回复简洁自然，符合日常交流语气

【最近对话】
{recent_memory}

【历史对话】
{history_memory}

# 用户最新问题
{user_input}
"""