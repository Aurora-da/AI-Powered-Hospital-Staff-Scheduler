from config import logger, MAX_MEMORY_LENGTH, MEMORY_PROMPT_TPL, RECENT_MEMORY_NUM
from llm_client import chat

# 全局记忆存储：列表中每个元素为字典{"user": 用户输入, "ai": AI回复}
# 新对话自动append到列表末尾，列表尾部为最新对话
chat_memory = []

def add_memory(user_input: str, ai_response: str):
    """添加对话记忆，超出最大条数则删除最早的记录，同时限制单条长度"""
    # 额外优化：限制单条对话的最大字符数，精简记忆
    MAX_SINGLE_LEN = 200
    user_input = user_input[:MAX_SINGLE_LEN] if len(user_input) > MAX_SINGLE_LEN else user_input
    ai_response = ai_response[:MAX_SINGLE_LEN] if len(ai_response) > MAX_SINGLE_LEN else ai_response
    
    chat_memory.append({"user": user_input, "ai": ai_response})
    if len(chat_memory) > MAX_MEMORY_LENGTH:
        chat_memory.pop(0)  # 删除最旧的对话
    logger.info(f"对话记忆已更新，当前记忆条数：{len(chat_memory)}")

# 【核心优化】重写记忆文本生成函数，实现分层权重
def get_memory_text() -> tuple[str, str]:
    """
    将记忆按权重分层，返回(最近对话文本, 历史对话文本)
    - 最近对话：最后RECENT_MEMORY_NUM条，倒序（最新的在最前），高权重
    - 历史对话：剩余条数，倒序，低权重
    """
    if not chat_memory:
        return "无", "无"
    
    # 先整体倒序：最新的对话在最前面
    reversed_memory = chat_memory[::-1]
    total = len(reversed_memory)
    
    # 拆分最近对话和历史对话
    recent_part = reversed_memory[:RECENT_MEMORY_NUM]
    history_part = reversed_memory[RECENT_MEMORY_NUM:] if total > RECENT_MEMORY_NUM else []
    
    # 生成最近对话文本（高权重）
    recent_text = ""
    for idx, item in enumerate(recent_part, 1):
        recent_text += f"{idx}. 用户：{item['user']}；AI：{item['ai']}\n"
    
    # 生成历史对话文本（低权重）
    history_text = ""
    for idx, item in enumerate(history_part, 1):
        history_text += f"{idx}. 用户：{item['user']}；AI：{item['ai']}\n"
    
    # 去除末尾换行，无内容则返回"无"
    return recent_text.strip() or "无", history_text.strip() or "无"

def clear_memory():
    """清空对话记忆"""
    chat_memory.clear()
    logger.info("对话记忆已清空")

# 【少量修改】通用对话处理，适配分层的记忆文本
def general_chat_handler(user_input: str) -> str:
    """通用对话处理，带权重记忆上下文调用LLM"""
    try:
        # 获取分层的记忆文本（最近+历史）
        recent_memory, history_memory = get_memory_text()
        # 拼接优化后的prompt（带权重规则）
        prompt = MEMORY_PROMPT_TPL.format(
            recent_memory=recent_memory,
            history_memory=history_memory,
            user_input=user_input
        )
        # 调用LLM
        response = chat(prompt)
        # 添加本次对话到记忆（最新对话，自动在列表尾部）
        add_memory(user_input, response)
        return response
    except Exception as e:
        logger.error(f"通用对话调用失败: {e}", exc_info=True)
        error_msg = "通用对话服务暂时不可用，请稍后再试"
        add_memory(user_input, error_msg)
        return error_msg