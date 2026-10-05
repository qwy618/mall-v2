"""接口请求/响应模型"""
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    token: str | None = None        # 会员 JWT（加购/下单接口透传）
    session_id: str | None = None   # 会话 id（Redis 会话记忆）
    as_system: bool = False         # True 时 message 作为「系统指令」注入（如用户已确认下单），
    #                                 前端点「确认下单」时必须为 True：SYSTEM_PROMPT 规则 13
    #                                 要求该指令以系统消息形式到达，LLM 才会调用 place_order


class ClearRequest(BaseModel):
    session_id: str | None = None   # 要清除的会话 id
