# model_client.py
from typing import List, Dict, Optional, Generator
import os
from openai import OpenAI

# ==================== 配置管理 ====================
try:
    from django.conf import settings as django_settings
except Exception:
    django_settings = None


def _get_setting_value(name: str, default: str = "") -> str:
    """优先从环境变量，其次Django settings，最后默认值。"""
    val = os.getenv(name)
    if val is not None and str(val).strip() != "":
        return str(val).strip()

    if django_settings is not None and hasattr(django_settings, name):
        s_val = getattr(django_settings, name)
        if s_val is not None and str(s_val).strip() != "":
            return str(s_val).strip()
    return default


# 核心配置
MODELSCOPE_API_KEY = _get_setting_value("MODELSCOPE_API_KEY")
MODELSCOPE_BASE_URL = _get_setting_value(
    "MODELSCOPE_BASE_URL", "https://api-inference.modelscope.cn/v1"
)
MODELSCOPE_MODEL_ID = _get_setting_value(
    "MODELSCOPE_MODEL_ID", "deepseek-ai/DeepSeek-V3.1"
)

# 系统提示词
_DEFAULT_SYSTEM_PROMPT = (
    "你是B站视频数据分析与可视化系统的AI助手。请用简体中文回复，"
    "风格简洁、专业，必要时给出分点、表格或代码示例。"
    "在解释与推荐时，尽量结合系统的功能模块(视频数据、推荐、可视化、词云等)。"
)


# ==================== 客户端初始化 ====================
def _get_client() -> OpenAI:
    """构造OpenAI兼容客户端（基于ModelScope网关）。"""
    if not MODELSCOPE_API_KEY:
        raise ValueError(
            "缺少AI配置，请在环境变量或Django settings中设置MODELSCOPE_API_KEY。"
        )
    return OpenAI(base_url=MODELSCOPE_BASE_URL, api_key=MODELSCOPE_API_KEY)


# ==================== 消息构造 ====================
def _build_messages(
    user_message: str,
    history: Optional[List[Dict[str, str]]] = None,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    构造符合OpenAI API格式的消息列表。
    """
    messages: List[Dict[str, str]] = []
    # 1. 系统消息
    messages.append(
        {
            "role": "system",
            "content": system_prompt.strip()
            if system_prompt
            else _DEFAULT_SYSTEM_PROMPT,
        }
    )
    # 2. 历史消息
    if history:
        for m in history:
            role = m.get("role")
            content = (m.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
    # 3. 当前用户消息
    messages.append({"role": "user", "content": (user_message or "").strip()})
    return messages


# ==================== 同步调用 ====================
def generate_chat_reply(
    user_message: str,
    history: Optional[List[Dict[str, str]]] = None,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    """
    同步生成一次性回复，返回完整字符串。
    """
    client = _get_client()
    messages = _build_messages(user_message, history, system_prompt)

    resp = client.chat.completions.create(
        model=MODELSCOPE_MODEL_ID,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )

    # 提取回复内容
    choice = resp.choices[0]
    message = getattr(choice, "message", None)
    if message and hasattr(message, "content"):
        return message.content
    # 兼容处理
    return getattr(choice, "text", "")


# ==================== 流式调用 ====================
def stream_chat_reply(
    user_message: str,
    history: Optional[List[Dict[str, str]]] = None,
    system_prompt: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> Generator[str, None, None]:
    """
    流式生成回复，每次yield一个片段。
    """
    client = _get_client()
    messages = _build_messages(user_message, history, system_prompt)

    stream = client.chat.completions.create(
        model=MODELSCOPE_MODEL_ID,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )

    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content is not None:
            yield content