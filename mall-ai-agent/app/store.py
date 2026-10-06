"""状态层（M1）：Redis 门面 —— 全项目**唯一** import redis 的地方。

职责：
  1) 会话历史：LangChain 消息列表（Redis List，一条消息一个元素）+ 归属校验 + 滑动 TTL
     —— 事实源，**只追加不裁剪**；预算裁剪是装配层（app/sessions.py）的事
  2) 订单草稿：preview_order 生成，place_order 原子消费（Lua）
  3) 幂等结果回放：draftId → orderId（防"网络重试把成功说成失败"）
  4) 装配诊断：上一次用了哪一级降级（可丢，仅供排查/验收）
  5) 历史摘要段（T3）：ai:summary:{sid}:seg:{i} + :index —— **派生缓存**，可丢可重算；
     人工回滚 = 删这些键（见 clear_summaries），原文毫发无损
  6) 上限裁剪（M1.5.4）：trim_oldest_messages + 审计键 ai:retention:{sid}:last
     —— **唯一真正丢数据的地方**，且只删"已被摘要覆盖"的轮（前置条件由 summarize 保证）

三条铁律：
  - **只用 JSON，禁用 pickle**：pickle 反序列化即执行任意代码，缓存被写入=RCE 面。
  - **不做鉴权判决，只提供事实**：本模块回答"这个 sid 属于谁"，判不判由调用方决定。
  - **Redis 不可用要大声报错**：静默返回空会让故障表现为"会话凭空消失"，极难排查。

db 选择：默认 db5（见 config.REDIS_URL），与 mall-portal 的 db0 物理隔离。
"""
from __future__ import annotations

import json
import time
import uuid

import redis

from . import config

# ---------------------------------------------------------------- 连接

# 连接池线程安全：LangGraph 的 executor 线程与 FastAPI 事件循环共用同一个 client
_client: redis.Redis | None = None


def client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            config.REDIS_URL,
            decode_responses=True,      # 读出来就是 str，省得处处 decode
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _client


def assert_available() -> None:
    """启动时自检。连不上就快速失败，并给出可操作的提示。"""
    try:
        client().ping()
    except redis.RedisError as e:
        raise RuntimeError(
            f"Redis 不可用（{_mask(config.REDIS_URL)}）：{e}\n"
            "请检查 REDIS_URL（.env）、Redis 是否启动、密码/防火墙是否正确。"
        ) from e


def _mask(url: str) -> str:
    """日志里隐藏 redis url 中的密码。"""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        cred, host = rest.rsplit("@", 1)
        if ":" in cred:
            user, _, _ = cred.partition(":")
            return f"{scheme}://{user}:***@{host}"
    return url


# ---------------------------------------------------------------- key 约定

SESSION_TTL = 7 * 24 * 3600      # 会话：7 天滑动
DRAFT_TTL = 15 * 60             # 草稿：15 分钟（过期价格/库存不该被拿来下单）
RESULT_TTL = 3600               # 结果回放：1 小时


def _k_messages(sid: str) -> str:
    return f"ai:session:{sid}:messages"


def _k_meta(sid: str) -> str:
    return f"ai:session:{sid}:meta"


def _k_draft(sid: str, member_id, draft_id: str) -> str:
    # 把 member_id 编进 key：归属由 key 空间天然保证，别人拿不到你的草稿
    return f"ai:draft:{sid}:{member_id}:{draft_id}"


def _k_result(draft_id: str) -> str:
    return f"ai:draft:result:{draft_id}"


def _k_assembly(sid: str) -> str:
    """上一次装配的诊断信息（用了哪一级、几进几出），只用于排查与验收，可丢。"""
    return f"ai:assembly:{sid}:last"


def _k_retention(sid: str) -> str:
    """最近一次上限裁剪的**审计记录**（删了哪几轮、由哪些摘要段兜底），可丢。

    保留它是因为"删数据"是唯一不可逆的操作——出问题时必须能追溯。
    """
    return f"ai:retention:{sid}:last"


def _k_summary_seg(sid: str, seg_id: int) -> str:
    return f"ai:summary:{sid}:seg:{seg_id}"


def _k_summary_index(sid: str) -> str:
    """段号 → 覆盖区间 + digest 的索引（Hash）。派生缓存，删掉即完成人工回滚。"""
    return f"ai:summary:{sid}:index"


def _k_summary_lock(sid: str) -> str:
    return f"ai:lock:summ:{sid}"


class SessionOwnershipError(Exception):
    """同一 sid 被不同登录用户写入——多半是 sid 被复用或泄漏，拒绝而不是覆盖。"""


# ---------------------------------------------------------------- 会话


def _migrate_if_string(sid: str) -> None:
    """存量数据迁移：`messages` 键由 String(JSON 数组) → List（每元素一条消息 JSON）。

    M1.5 把会话从"单个 JSON 串"改成 List：追加是 RPUSH（O(1)），
    不必每轮把整个会话读出来再整体写回。旧数据在首次触碰时透明转换，幂等可重跑。
    """
    key = _k_messages(sid)
    c = client()
    try:
        ktype = c.type(key)
    except redis.RedisError:  # pragma: no cover —— 连接问题交由上层 assert_available 暴露
        return
    if ktype != "string":
        return

    raw = c.get(key)
    try:
        items = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        items = []
    if not isinstance(items, list):
        items = []

    pipe = c.pipeline()
    pipe.delete(key)
    for it in items:
        pipe.rpush(key, json.dumps(it, ensure_ascii=False))
    pipe.expire(key, SESSION_TTL)
    pipe.execute()


def load_messages(sid: str, member_id=None) -> list[dict]:
    """读会话消息（已序列化的 dict 列表，**全量**，按时间正序）。

    归属校验：meta 里记了 owner 且与当前 member_id 不一致 → 视为**空会话**
    （防"换个 sid 读别人聊天记录"）；未登录成员（None）不做限制。
    读取时顺带刷新 TTL，保证"一直在聊的会话永不过期"。

    注意：这是**事实源**，读到的就是全部原文；做预算裁剪是装配层（sessions）的事。
    """
    owner = session_owner(sid)
    if owner is not None and member_id is not None and str(owner) != str(member_id):
        return []

    _migrate_if_string(sid)
    raw = client().lrange(_k_messages(sid), 0, -1)

    messages: list[dict] = []
    for r in raw:
        try:
            obj = json.loads(r)
        except json.JSONDecodeError:
            continue                 # 单条脏数据跳过，不让整轮对话崩掉
        if isinstance(obj, dict):
            messages.append(obj)

    # 滑动过期
    pipe = client().pipeline()
    pipe.expire(_k_messages(sid), SESSION_TTL)
    pipe.expire(_k_meta(sid), SESSION_TTL)
    pipe.execute()
    return messages


def _touch_meta(pipe, sid: str, member_id, count: int, owner,
                rounds_abs: int | None = None, rounds_delta: int = 0,
                bytes_abs: int | None = None, bytes_delta: int = 0) -> None:
    meta = {
        "lastActive": str(int(time.time())),
        "msgCount": str(count),
    }
    if member_id is not None:
        meta["memberId"] = str(member_id)
    elif owner is not None:
        meta["memberId"] = str(owner)      # 游客轮次不覆盖已有 owner
    pipe.hset(_k_meta(sid), mapping=meta)
    # 轮数（HumanMessage 条数）单独维护：供摘要调度的 O(1) 门控，避免每轮 LRANGE 全量
    if rounds_abs is not None:
        pipe.hset(_k_meta(sid), "rounds", str(int(rounds_abs)))
    elif rounds_delta:
        pipe.hincrby(_k_meta(sid), "rounds", int(rounds_delta))
    # 载荷字节数（近似）：供上限裁剪的 O(1) 门控，避免每轮 MEMORY USAGE / LRANGE
    if bytes_abs is not None:
        pipe.hset(_k_meta(sid), "bytes", str(max(0, int(bytes_abs))))
    elif bytes_delta:
        pipe.hincrby(_k_meta(sid), "bytes", int(bytes_delta))
    pipe.expire(_k_meta(sid), SESSION_TTL)


def _payload_bytes(dicts: list[dict]) -> int:
    """消息序列化后的字节数（与真正 RPUSH 进 Redis 的字符串一致）。"""
    return sum(len(json.dumps(m, ensure_ascii=False).encode("utf-8")) for m in dicts)



def count_messages(sid: str) -> int:
    """会话消息条数（LLEN，不读内容）。"""
    _migrate_if_string(sid)
    return int(client().llen(_k_messages(sid)))


def save_messages(sid: str, messages: list[dict], member_id=None) -> None:
    """**覆盖**写入会话消息（重置为给定列表）。

    生产写入路径已改为 append_messages（只追加）；本函数保留给"重置/测试"使用，
    因为覆盖写会丢掉历史，日常不要用它。
    """
    owner = session_owner(sid)
    if owner is not None and member_id is not None and str(owner) != str(member_id):
        raise SessionOwnershipError(
            f"会话 {sid} 属于会员 {owner}，拒绝被会员 {member_id} 覆盖"
        )

    key = _k_messages(sid)
    pipe = client().pipeline()
    pipe.delete(key)                    # 先删：兼容旧的 String 类型键
    for m in messages:
        pipe.rpush(key, json.dumps(m, ensure_ascii=False))
    pipe.expire(key, SESSION_TTL)
    # 重置即"时间线归零"：轮数、字节、已裁剪轮数都要跟着重算
    pipe.hset(_k_meta(sid), "trimmedRounds", "0")
    _touch_meta(pipe, sid, member_id, len(messages), owner,
                rounds_abs=_count_rounds(messages), bytes_abs=_payload_bytes(messages))
    pipe.execute()


def _count_rounds(messages: list[dict]) -> int:
    """消息列表里的"轮数" = HumanMessage 条数（每条用户消息开启一轮）。"""
    return sum(1 for m in messages if isinstance(m, dict) and m.get("type") == "human")



def append_messages(sid: str, messages: list[dict], member_id=None) -> None:
    """**追加**写入会话消息（事实源只增不减）。

    这是生产的写路径：本轮新增了几条就 RPUSH 几条，
    不再"读出整个会话 → 改 → 整个写回"，因此与对话长度无关（O(1)）。
    """
    if not messages:
        return
    owner = session_owner(sid)
    if owner is not None and member_id is not None and str(owner) != str(member_id):
        raise SessionOwnershipError(
            f"会话 {sid} 属于会员 {owner}，拒绝被会员 {member_id} 追加"
        )

    _migrate_if_string(sid)             # 旧的 String 键必须先转 List，否则 RPUSH 报 WRONGTYPE
    key = _k_messages(sid)
    pipe = client().pipeline()
    for m in messages:
        pipe.rpush(key, json.dumps(m, ensure_ascii=False))
    pipe.expire(key, SESSION_TTL)
    pipe.execute()

    # meta 的 msgCount 用 LLEN 实测（并发下本地计数会偏）；轮数/字节按新增量累加
    pipe = client().pipeline()
    _touch_meta(pipe, sid, member_id, _llen(key), owner,
                rounds_delta=_count_rounds(messages), bytes_delta=_payload_bytes(messages))
    pipe.execute()


def _llen(key: str) -> int:
    return int(client().llen(key))


def save_assembly(sid: str, info: dict) -> None:
    """记录上一次装配用了哪一级（诊断/验收用，15 分钟过期）。"""
    try:
        client().set(_k_assembly(sid), json.dumps(info, ensure_ascii=False), ex=15 * 60)
    except redis.RedisError:  # pragma: no cover —— 诊断信息写失败不该影响对话
        pass


def load_assembly(sid: str) -> dict:
    raw = client().get(_k_assembly(sid))
    try:
        obj = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        obj = {}
    return obj if isinstance(obj, dict) else {}


def save_retention(sid: str, audit: dict) -> None:
    """写上限裁剪的审计记录（删数据是唯一不可逆操作，必须留痕）。"""
    try:
        client().set(_k_retention(sid), json.dumps(audit, ensure_ascii=False), ex=15 * 60)
    except redis.RedisError:  # pragma: no cover —— 审计写失败不该影响对话
        pass


def load_retention(sid: str) -> dict:
    raw = client().get(_k_retention(sid))
    try:
        obj = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        obj = {}
    return obj if isinstance(obj, dict) else {}


def session_owner(sid: str) -> str | None:
    """该会话归属的会员 id（未记录或游客会话返回 None）。"""
    v = client().hget(_k_meta(sid), "memberId")
    return v or None


def clear_session(sid: str) -> None:
    """清空会话（前端「清除会话」按钮）。只删本会话的键，绝不用 FLUSHDB。"""
    clear_summaries(sid)                # 摘要段是派生缓存，随会话一起清
    client().delete(_k_messages(sid), _k_meta(sid), _k_assembly(sid), _k_retention(sid))


# ---------------------------------------------------------------- 轮数元数据
#
# 摘要调度的门控要"够快"：每轮请求都 LRANGE 全量去数轮数是浪费。
# 所以在 meta 里维护两个 O(1) 就能读到的计数：
#   rounds      —— 会话累计轮数（HumanMessage 条数）
#   summRounds  —— 已被摘要覆盖的轮数（前缀长度；摘要永远从第 0 轮往后连续生成）


def session_rounds(sid: str) -> int:
    return _meta_int(sid, "rounds")


def session_summary_rounds(sid: str) -> int:
    return _meta_int(sid, "summRounds")


def session_trimmed_rounds(sid: str) -> int:
    """已被上限裁剪从**头部**删掉的轮数（绝对轮号的前缀长度）。

    有了它，摘要段的"绝对轮号 [rFrom, rTo)"才能映射回当前消息下标：
    当前第 k 条轮 = 绝对第 `trimmedRounds + k` 轮。因此裁剪后无需改写段记录。
    """
    return _meta_int(sid, "trimmedRounds")


def session_bytes(sid: str) -> int:
    """会话消息的近似字节数（meta O(1) 读；老会话无记录时回填一次缓存）。"""
    v = client().hget(_k_meta(sid), "bytes")
    if v is not None:
        try:
            return max(0, int(v))
        except (TypeError, ValueError):
            pass
    total = _payload_bytes_raw(_k_messages(sid))
    client().hset(_k_meta(sid), "bytes", str(total))
    client().expire(_k_meta(sid), SESSION_TTL)
    return total


def _payload_bytes_raw(key: str) -> int:
    return sum(len(r.encode("utf-8")) for r in client().lrange(key, 0, -1))


def set_session_rounds(sid: str, n: int) -> None:
    client().hset(_k_meta(sid), "rounds", str(int(n)))
    client().expire(_k_meta(sid), SESSION_TTL)


def set_session_summary_rounds(sid: str, n: int) -> None:
    client().hset(_k_meta(sid), "summRounds", str(int(n)))
    client().expire(_k_meta(sid), SESSION_TTL)


def trim_oldest_messages(sid: str, count: int, trimmed_rounds_delta: int = 0) -> int:
    """上限裁剪的唯一原语：从**头部** `LTRIM` 掉 `count` 条消息。

    - 只有"已被摘要覆盖"的轮才允许走到这里（前置条件由调用方保证，见 summarize.maybe_trim）。
    - 字节扣减用**被删内容的真实序列化长度**，所以 meta.bytes 不会因估算而漂移。
    - `rounds` 是会话**累计**轮数（绝对、单调），裁剪不动它；只累加 `trimmedRounds`。
    """
    if count <= 0:
        return 0
    _migrate_if_string(sid)
    key = _k_messages(sid)
    n = _llen(key)
    if count > n:
        count = n
    if count <= 0:
        return 0

    doomed = client().lrange(key, 0, count - 1)
    bytes_delta = sum(len(r.encode("utf-8")) for r in doomed)
    cur_bytes = session_bytes(sid)          # 必须在 LTRIM **之前**读（否则读到的是删后的值）

    pipe = client().pipeline()
    pipe.ltrim(key, count, -1)
    pipe.expire(key, SESSION_TTL)
    pipe.execute()

    pipe = client().pipeline()
    pipe.hset(_k_meta(sid), mapping={
        "msgCount": str(_llen(key)),
        "bytes": str(max(0, cur_bytes - bytes_delta)),
    })
    if trimmed_rounds_delta:
        pipe.hincrby(_k_meta(sid), "trimmedRounds", int(trimmed_rounds_delta))
    pipe.expire(_k_meta(sid), SESSION_TTL)
    pipe.execute()
    return count


def _meta_int(sid: str, field: str) -> int:
    v = client().hget(_k_meta(sid), field)
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------- 历史摘要段（T3，派生）
#
# 分段链：每 SUMMARY_SEG_ROUNDS 轮 → 一段 ai:summary:{sid}:seg:{i}。
# 段是**派生缓存**：丢了下轮装配退回 T2，功能不受影响（见 sessions.inject_summaries）。
# 写入顺序即回滚协议：先写段本体 → 再更新索引；中间失败 = 索引里没有它 = 等于没压过。


def save_segment(sid: str, seg_id: int, record: dict) -> None:
    """写一个摘要段。`record` 含 text 与元数据（区间/digest/level）。"""
    meta = {k: v for k, v in record.items() if k != "text"}
    pipe = client().pipeline()
    pipe.set(_k_summary_seg(sid, seg_id), json.dumps(record, ensure_ascii=False),
             ex=SESSION_TTL)
    pipe.hset(_k_summary_index(sid), str(seg_id), json.dumps(meta, ensure_ascii=False))
    pipe.expire(_k_summary_index(sid), SESSION_TTL)
    pipe.execute()


def load_segment(sid: str, seg_id: int) -> dict | None:
    raw = client().get(_k_summary_seg(sid, seg_id))
    try:
        obj = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def load_summary_index(sid: str) -> dict[int, dict]:
    """读索引：{段号: 元数据}。脏数据单条跳过，不让整轮装配崩。"""
    raw = client().hgetall(_k_summary_index(sid)) or {}
    out: dict[int, dict] = {}
    for k, v in raw.items():
        try:
            seg_id = int(k)
            meta = json.loads(v)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(meta, dict):
            out[seg_id] = meta
    return out


def delete_segment(sid: str, seg_id: int) -> None:
    pipe = client().pipeline()
    pipe.delete(_k_summary_seg(sid, seg_id))
    pipe.hdel(_k_summary_index(sid), str(seg_id))
    pipe.execute()


def clear_summaries(sid: str) -> None:
    """人工回滚：删掉全部派生摘要。下轮装配自动退回 T2/T1，对话功能不受影响。"""
    idx = load_summary_index(sid)
    pipe = client().pipeline()
    for seg_id in idx:
        pipe.delete(_k_summary_seg(sid, seg_id))
    pipe.delete(_k_summary_index(sid))
    pipe.hdel(_k_meta(sid), "summRounds")     # 覆盖进度归零，下次可重新压
    pipe.execute()


# 单飞锁：只有持有者能释放（比对 token 再 DEL），避免"锁超时后被别人抢到、又被前一个释放"
_LOCK_RELEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


def acquire_summary_lock(sid: str, token: str, ttl: int | None = None) -> bool:
    """抢单飞锁。返回是否抢到（抢不到说明别的线程/worker 正在压）。"""
    return bool(client().set(_k_summary_lock(sid), token, nx=True,
                             ex=ttl or config.SUMMARY_LOCK_TTL))


def release_summary_lock(sid: str, token: str) -> None:
    client().eval(_LOCK_RELEASE_LUA, 1, _k_summary_lock(sid), token)


# ---------------------------------------------------------------- 订单草稿

# 原子消费：读出即删除，一次调用完成"读-判-删"，并发点两次只有一个拿到
_POP_LUA = """
local v = redis.call('GET', KEYS[1])
if v then redis.call('DEL', KEYS[1]) end
return v
"""

_pop_script = None


def _pop(sid: str, member_id, draft_id: str) -> str | None:
    global _pop_script
    if _pop_script is None:
        _pop_script = client().register_script(_POP_LUA)
    return _pop_script(keys=[_k_draft(sid, member_id, draft_id)])


def create_draft(sid: str, member_id, payload: dict) -> str:
    """落一份订单草稿，返回 draft_id。payload 应含"下单参数 + 金额快照"。"""
    draft_id = uuid.uuid4().hex[:12]
    body = json.dumps({"memberId": None if member_id is None else str(member_id),
                       "payload": payload}, ensure_ascii=False)
    client().set(_k_draft(sid, member_id, draft_id), body, ex=DRAFT_TTL)
    return draft_id


def get_draft(sid: str, member_id, draft_id: str) -> dict | None:
    """只读草稿（不消费）。返回 payload 部分。"""
    raw = client().get(_k_draft(sid, member_id, draft_id))
    return _parse_draft(raw, member_id)


def pop_draft(sid: str, member_id, draft_id: str) -> dict | None:
    """**原子消费**草稿；返回 payload 部分。并发/重复消费只会有一个成功。"""
    return _parse_draft(_pop(sid, member_id, draft_id), member_id)


def _parse_draft(raw, member_id) -> dict | None:
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    if member_id is not None and obj.get("memberId") not in (None, str(member_id)):
        return None
    return obj.get("payload")


# ---------------------------------------------------------------- 幂等结果回放


def remember_result(draft_id: str, order_id) -> None:
    """记下"这个草稿已经下过单"，供重试时原样回放。"""
    client().set(_k_result(draft_id), str(order_id), ex=RESULT_TTL)


def recall_result(draft_id: str) -> int | None:
    """查"这个草稿是否已经下过单"；命中返回 orderId，否则 None。"""
    v = client().get(_k_result(draft_id))
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- RAG 索引（M3）

# 索引元数据：仅运维可见（"索引新不新"），**绝不向用户暴露索引时间**（M3 §5.4）
RAG_META_TTL = 30 * 24 * 3600   # 30 天：只是诊断信息，重建时会刷新


def _k_rag_meta() -> str:
    return "ai:rag:meta"


def _k_rag_lock() -> str:
    return "ai:rag:lock"


def save_rag_meta(meta: dict) -> None:
    """写索引元数据（Hash）。字段值统一转字符串，读取时由调用方还原类型。"""
    key = _k_rag_meta()
    client().hset(key, mapping={k: str(v) for k, v in meta.items()})
    client().expire(key, RAG_META_TTL)


def load_rag_meta() -> dict:
    """读索引元数据；不存在返回空 dict（调用方据此判定"索引缺失"）。"""
    raw = client().hgetall(_k_rag_meta())
    return {k.decode() if isinstance(k, bytes) else k:
            v.decode() if isinstance(v, bytes) else v
            for k, v in (raw or {}).items()}


def acquire_rag_lock(token: str, ttl: int | None = None) -> bool:
    """抢索引构建的单飞锁（与 M1.5 摘要单飞同款）——多 worker 只有一个真正重建。"""
    return bool(client().set(_k_rag_lock(), token, nx=True,
                             ex=ttl or config.RAG_LOCK_TTL))


def release_rag_lock(token: str) -> None:
    client().eval(_LOCK_RELEASE_LUA, 1, _k_rag_lock(), token)


def peek_rag_lock() -> bool:
    """锁是否被持有（`--check` 用；不参与判断，只做诊断）。"""
    return bool(client().exists(_k_rag_lock()))


# ---------------------------------------------------------------- 治理（M4）

# INCR + 首次设 TTL，原子完成。
# 为什么必须原子：`INCR` 后 `EXPIRE` 分两步时，若进程在中间异常/被杀，
# 会留下**没有 TTL 的计数键 → 计数永不归零**，该身份在该窗口被永久限死（极难排查）。
# 为什么只在 n==1 时设：若每次 INCR 都续期，窗口会退化成"最后一次请求后 N 秒"
# 即滑动窗口——与"按分钟固定窗口"的语义不符，攻击者可持续续期永不被限。
_INCR_WINDOW_LUA = (
    "local n = redis.call('INCR', KEYS[1]) "
    "if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end "
    "return n"
)

# 累加用量 + 仅在缺 TTL 时补齐（用于 token 总量，多轮 INCRBY 不重置窗口）
_ADD_TOKENS_LUA = (
    "local n = redis.call('INCRBY', KEYS[1], ARGV[1]) "
    "if redis.call('TTL', KEYS[1]) < 0 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end "
    "return n"
)

_RATE_TTL_SLACK = 90              # 分钟桶的冗余 TTL
_QUOTA_TTL_SLACK = 86400 + 90     # 日桶的冗余 TTL（跨日换 key，无需清理任务）


def _k_rate(subject: str, bucket: str) -> str:
    """限流键。**桶名进 key** → 天然按分钟重置，不需要"读-判断-重置"三步。"""
    return f"ai:rate:{subject}:{bucket}"


def _k_quota(subject: str, day: str) -> str:
    return f"ai:quota:{subject}:{day}"


def _k_token_day(day: str) -> str:
    """全站当日 token 总量。⚠️ 这里**没有 subject**——它是全局计数，不是一个用户的。"""
    return f"ai:token:day:{day}"


def hit_rate(subject: str, ttl: int = _RATE_TTL_SLACK) -> int:
    """当前分钟桶累计次数（**含本次**）。先计数再判断——并发下才是精确的。"""
    return int(client().eval(_INCR_WINDOW_LUA, 1,
                             _k_rate(subject, time.strftime("%Y%m%d%H%M")), ttl))


def peek_rate(subject: str) -> int:
    """当前分钟桶次数，不递增（验收/诊断用）。"""
    return _as_int(client().get(_k_rate(subject, time.strftime("%Y%m%d%H%M"))))


def hit_quota(subject: str, ttl: int = _QUOTA_TTL_SLACK) -> int:
    """当日累计次数（含本次）。跨日自动换 key。"""
    return int(client().eval(_INCR_WINDOW_LUA, 1,
                             _k_quota(subject, time.strftime("%Y%m%d")), ttl))


def peek_quota(subject: str) -> int:
    return _as_int(client().get(_k_quota(subject, time.strftime("%Y%m%d"))))


def add_tokens(n: int, ttl: int = _QUOTA_TTL_SLACK) -> int:
    """累加全站当日 token 用量，返回累计值。n<=0 时只读不写。"""
    if n <= 0:
        return peek_tokens()
    return int(client().eval(_ADD_TOKENS_LUA, 1,
                             _k_token_day(time.strftime("%Y%m%d")), n, ttl))


def peek_tokens() -> int:
    return _as_int(client().get(_k_token_day(time.strftime("%Y%m%d"))))


def _as_int(v) -> int:
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0
