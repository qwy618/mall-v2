"""mall-v2 portal 的 HTTP 客户端。

两条必须遵守的约定：

1. **接口失败也常返回 HTTP 200**，真实状态在 body 的 `code` 字段里——
   业务失败/无权限（403）都是 `body.code` 标识，成功才是 200。
   所以统一先解析 JSON，再按 `body.code` 判断成败。

2. **未登录是 HTTP 401 + `body.code=401`**（portal 的 RestAuthenticationEntryPoint）。
   这里必须在 `raise_for_status()` **之前**判定 401，否则会被当成普通 HTTP 错误，
   `NeedLoginError` 就永远抛不出来，前端「引导登录」的整条链路会断。
"""
import time

import httpx
from langchain_core.tools import ToolException

from .. import config

TIMEOUT = 30


class NeedLoginError(Exception):
    """用户未登录或登录已过期——需前端引导登录，而不是当对话错误处理。

    设计要点：继承普通 Exception（不是 ToolException），
    这样它会穿透 LangGraph 工具节点的 ToolException 捕获层，
    一路冒泡到 main.py 的流式循环，被 except 捕获后转成 need_login SSE 事件。
    """
    pass


def _auth_header(token: str | None) -> dict:
    """归一化 token：前端存储的 token 可能自带 tokenHead（Bearer 前缀），
    这里统一去掉已有前缀再加 Bearer，避免出现 "Bearer Bearer xxx"。
    portal 实测：必须 Bearer 前缀，裸 token 会 401。"""
    if not token:
        return {}
    t = token.strip()
    if t.lower().startswith("bearer "):
        t = t[len("bearer "):]
    return {"Authorization": f"Bearer {t}"}


def _request(method: str, base_url: str, path: str, *,
             params: dict | None = None,
             body: dict | list | None = None,
             token: str | None = None) -> dict:
    url = f"{base_url}{path}"
    try:
        resp = httpx.request(method, url, params=params, json=body,
                             headers=_auth_header(token), timeout=TIMEOUT)
    except httpx.HTTPError as e:
        # ToolException 的消息会回传给 LLM，让它知道「调用失败」并调整策略
        raise ToolException(f"调用商城接口失败（网络/HTTP 错误）: {e}") from e

    # 未登录：HTTP 401（body 同样是 code=401）。必须先于 raise_for_status 判定
    if resp.status_code == 401:
        raise NeedLoginError("用户未登录或登录已过期")

    try:
        data = resp.json()
    except ValueError:
        resp.raise_for_status()
        raise ToolException(f"商城接口返回非 JSON 内容（HTTP {resp.status_code}）")

    code = data.get("code")
    if code not in (200, None):
        if code == 401:
            raise NeedLoginError("用户未登录或登录已过期")
        raise ToolException(f"商城接口返回错误 code={code} message={data.get('message')}")
    return data


def api_get(base_url: str, path: str, params: dict | None = None, token: str | None = None) -> dict:
    return _request("GET", base_url, path, params=params, token=token)


def api_post(base_url: str, path: str, params: dict | None = None,
             body: dict | list | None = None, token: str | None = None) -> dict:
    """POST：`params` 走查询串（对应后端 `@RequestParam`），`body` 走 JSON（对应 `@RequestBody`）。"""
    return _request("POST", base_url, path, params=params, body=body, token=token)


def api_delete(base_url: str, path: str, params: dict | None = None, token: str | None = None) -> dict:
    return _request("DELETE", base_url, path, params=params, token=token)


# ---------------------------------------------------------------- 会员身份

_MEMBER_TTL = 60
# token -> (过期时间戳, memberId)。进程内缓存：memberId 不会变，短 TTL 只为兜"换用户"
_member_cache: dict[str, tuple[float, int]] = {}


def resolve_member_id(token: str | None) -> int | None:
    """用 token 换当前会员 id（未登录/过期返回 None）。

    M1 用途：把会话绑定到会员，防"换个 sid 读别人聊天记录"。

    为什么在这里而不是 store：这是纯 HTTP 关注点（store 只管存取、不管鉴权）。
    为什么返回 None 而不是抛异常：**未登录是合法状态**（游客可只读问答），
    不该在解析身份这一步就打断对话——真正需要登录的加购/下单工具会各自抛 NeedLoginError。
    """
    if not token:
        return None
    now = time.time()
    hit = _member_cache.get(token)
    if hit and hit[0] > now:
        return hit[1]
    try:
        data = api_get(config.PORTAL_BASE_URL, "/member/info", token=token)
    except Exception:  # noqa: BLE001 —— NeedLoginError/ToolException 都算"身份不明"
        return None
    member = data.get("data") or {}
    mid = member.get("id")
    if mid is None:
        return None
    _member_cache[token] = (now + _MEMBER_TTL, int(mid))
    return int(mid)
