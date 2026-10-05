"""订单草稿（M1：Redis 版）。

preview_order 生成草稿，用户点「确认下单」后 place_order 才真正下单。

安全铁律的落地：
  - 下单参数（购物车条目、地址、金额）只能来自草稿，LLM 无法编造；
  - 草稿**一次性使用**且**原子消费**（store 的 Lua），并发点两次只有一个成功；
  - 草稿 key 里编入 member_id → 归属由 key 空间保证。

本模块只是 store 的薄封装，保留 orders.xxx 这个调用点，方便将来换存储。
"""
from __future__ import annotations

from . import store


def create_draft(session_id: str, member_id, data: dict) -> str:
    """落一份草稿，返回 draft_id。data 应含「下单参数 + 金额快照」。"""
    return store.create_draft(session_id, member_id, data)


def get_draft(session_id: str, member_id, draft_id: str) -> dict | None:
    """只读草稿（不消费）。"""
    return store.get_draft(session_id, member_id, draft_id)


def pop_draft(session_id: str, member_id, draft_id: str) -> dict | None:
    """**原子消费**草稿。返回 None = 不存在 / 已过期 / 已被消费。"""
    return store.pop_draft(session_id, member_id, draft_id)


# ---------------------------------------------------------------- 幂等结果回放


def remember_result(draft_id: str, order_id) -> None:
    """记下"这份草稿已经下过单"（TTL 1h），供网络重试时原样回放。"""
    store.remember_result(draft_id, order_id)


def recall_result(draft_id: str) -> int | None:
    """查"这份草稿是否已经下过单"，命中返回 orderId。"""
    return store.recall_result(draft_id)
