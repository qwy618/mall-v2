"""LLM 工厂：DeepSeek 走 OpenAI 兼容模式，LangChain 直接复用 ChatOpenAI"""
from langchain_openai import ChatOpenAI

from . import config


def get_llm(temperature: float = 0.1, model: str | None = None) -> ChatOpenAI:
    """构建 LLM。model 为空用主模型；传入则用该模型（M4 成本超阈时切 fallback）。

    ⚠️ `timeout` 必须显式设置：不设的话上游卡住时请求会**一直挂着**——
    SSE 连接既不返回也不报错，是线上最难排查的一类故障（用户以为在"思考"）。

    `max_retries` 默认 0：重试会成倍放大 token 消耗，而用户已经感觉到"卡住"了，
    此时静默重试不如直接告诉他稍后再试。
    """
    if not config.DEEPSEEK_API_KEY:
        raise RuntimeError(
            "DEEPSEEK_API_KEY 未配置：在系统环境变量或 .env 中设置 DeepSeek 平台创建的 API Key")
    return ChatOpenAI(
        model=model or config.DEEPSEEK_MODEL,
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
        temperature=temperature,
        timeout=config.LLM_TIMEOUT,
        max_retries=config.LLM_MAX_RETRIES,
    )
