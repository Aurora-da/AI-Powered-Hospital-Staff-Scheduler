import requests
import time
from config import API_URL, SILICONFLOW_API_KEY, MODEL_NAME, LLM_MAX_RETRIES, logger

def chat(prompt: str) -> str:
    """调用LLM接口，带重试机制"""
    if not SILICONFLOW_API_KEY:
        raise ValueError("未配置SILICONFLOW_API_KEY，请检查.env文件")
    
    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是严格遵守格式要求的JSON输出助手，只输出JSON格式内容，不要添加额外解释。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }
    
    for retry in range(LLM_MAX_RETRIES):
        try:
            response = requests.post(API_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        except requests.RequestException as e:
            logger.error(f"LLM调用失败（第{retry+1}次）: {e}")
            if retry == LLM_MAX_RETRIES - 1:
                raise RuntimeError(f"LLM调用失败（重试{LLM_MAX_RETRIES}次）: {e}")
            time.sleep(2 ** retry)  # 指数退避重试