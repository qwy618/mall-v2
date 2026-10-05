"""LLM 工厂：DeepSeek 走 OpenAI 兼容模式，LangChain 直接复用 ChatOpenAI"""
from langchain_openai import ChatOpenAI

from . import config


def get_llm(temperature: float = 0.1) -> ChatOpenAI:
    if not config.DEEPSEEK_API_KEY:
        raise RuntimeError(
            "DEEPSEEK_API_KEY 未配置：在系统环境变量或 .env 中设置 DeepSeek 平台创建的 API Key")
    return ChatOpenAI(
        model=config.DEEPSEEK_MODEL,
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
        temperature=temperature,
    )
