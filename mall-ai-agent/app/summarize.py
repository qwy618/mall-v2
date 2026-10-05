"""T3 历史摘要：分段链压缩（M1.5.3）+ 单会话上限裁剪（M1.5.4）。

职责边界（重要）：
  - **本模块只负责"压"与"删"**：把热区之外的旧轮压成分段摘要；达上限时删最旧轮。
  - **"读 + 校验 + 注入"在 app/sessions.py**（`inject_summaries` / `verified_segments`）。
    这样装配是纯只读的，压缩失败/未被调度都不会影响任何一轮对话。

四条纪律（对齐 docs/M1.5 §2 / §5 / §6）：
  1. **原文不动**：`run_once` 永不 SET/DEL/LTRIM `ai:session:{sid}:messages`。
     唯一的例外是 `maybe_trim` 的上限裁剪（§4.3）—— 它也只删"已被摘要覆盖"的轮。
  2. **可回滚**：先写段 → 再更新索引；中间失败 = 索引里没有它 = 等于没压过。
     人工回滚 = `store.clear_summaries(sid)`，下轮装配自动退回 T2。
  3. **惰性异步**：`maybe_schedule()` 立即返回，真正压缩在后台线程；本轮先用 T1/T2 兜底。
  4. **单飞**：抢 `ai:lock:summ:{sid}`，抢不到就跳过（别的线程/worker 在压）。

分段链：
  每 `SUMMARY_SEG_ROUNDS` 轮 → 一段（level=1）；
  段数超过 `SUMMARY_ROLLUP_SEGS` → 把最旧的若干段**滚压**成更高层的一段（level+1）。
  只往后追加、前缀尽量不变 → 对 DeepSeek 的 prompt 前缀缓存友好（见 §6.3）。

轮号是**绝对**的（从会话诞生起累加，不因裁剪而重编号）：`base = trimmedRounds`
是已被裁剪的头部轮数，当前第 k 条轮 = 绝对第 `base + k` 轮。
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid

from langchain_core.messages import HumanMessage, SystemMessage

from . import config, sessions, store
from .llm import get_llm
from .prompts import SUMMARY_ROLLUP_PROMPT, SUMMARY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# 单条消息送进压缩前的最长字符（工具原始 JSON 可能是几 KB，压缩器只需要要点）
_RENDER_LIMIT = 600


# ---------------------------------------------------------------- 调度（惰性异步）


def maybe_schedule(sid: str, member_id=None) -> bool:
    """判定是否需要压缩；需要就**后台**去做。绝不阻塞调用方。

    返回是否真的投递了后台任务（便于测试与观测）。
    门控分三步，越靠前越便宜：
      ① 配置开关；
      ② O(1) 读 meta 的轮数/覆盖进度，判断"是否攒够一段"（避免每轮全量 LRANGE）；
      ③ 抢单飞锁——抢不到说明已有任务在跑，直接返回。
    """
    if not config.SUMMARY_ENABLED:
        return False

    try:
        rounds = store.session_rounds(sid)
        if rounds <= 0:
            # 老会话（M1.5.3 之前建的）meta 里没有 rounds：用"每轮≥2条消息"粗判
            rounds = store.count_messages(sid) // 2
        safe = max(0, rounds - sessions.HOT_ROUNDS)          # 热区之外才可压
        pending = safe - store.session_summary_rounds(sid)
        diag = store.load_assembly(sid)
        # 上下文已经超预算（装配降到 T3）→ 尽早压；否则攒批压（保护前缀缓存、省 LLM 调用）
        force = diag.get("level") == "T3"
        threshold = config.SUMMARY_SEG_ROUNDS if force else \
            max(config.SUMMARY_SEG_ROUNDS, config.SUMMARY_TRIGGER_UNSUMMARIZED)
        if pending < threshold:
            return False
    except Exception as e:                                    # noqa: BLE001
        logger.debug("摘要调度跳过（读元数据失败 sid=%s）：%s", sid, e)
        return False

    token = uuid.uuid4().hex
    try:
        if not store.acquire_summary_lock(sid, token):
            return False                                     # 已有任务在跑
    except Exception as e:                                    # noqa: BLE001
        logger.debug("摘要调度跳过（抢锁失败 sid=%s）：%s", sid, e)
        return False

    threading.Thread(target=_worker, args=(sid, member_id, token),
                     name=f"summary-{sid}", daemon=True).start()
    return True


def _worker(sid: str, member_id, token: str) -> None:
    """后台线程主体：压完释放锁。任何异常都不能外泄（后台线程里抛异常=静默丢失）。"""
    try:
        made = run_once(sid, member_id)
        if made:
            logger.info("摘要压缩完成：sid=%s 新压 %d 段", sid, made)
    except Exception as e:                                    # noqa: BLE001
        logger.warning("后台摘要任务失败（sid=%s）：%s", sid, e)
    finally:
        try:
            store.release_summary_lock(sid, token)
        except Exception:                                     # noqa: BLE001
            pass


# ---------------------------------------------------------------- 上限裁剪（M1.5.4）


def maybe_trim(sid: str, member_id=None) -> dict:
    """单会话上限裁剪：**达上限才删最旧**，且只删"已被摘要覆盖"的轮。

    与 `maybe_schedule` 的分工：调度负责"压"，本函数负责"删"。删除是 M1.5 里**唯一不可逆**
    的操作，所以前置条件是**硬性**的——要删的轮必须已被摘要覆盖；否则宁可先让会话超限、
    异步补压，下一轮再删（绝不为了压体积而丢弃唯一记录）。

    安全性来自"轮号绝对、裁剪无需改写段"（见 sessions.verified_segments）：
    这里只 `LTRIM` 消息 + 累加 `trimmedRounds`，摘要段记录原封不动。

    返回审计记录（同时写 `ai:retention:{sid}:last`）；无动作返回 {}。
    """
    max_rounds = config.SESSION_MAX_ROUNDS
    max_bytes = config.SESSION_MAX_BYTES
    if max_rounds <= 0 and max_bytes <= 0:
        return {}

    rounds = store.session_rounds(sid)                   # 绝对累计轮数
    trimmed = store.session_trimmed_rounds(sid)
    present = max(0, rounds - trimmed)                   # 当前在库轮数
    nbytes = store.session_bytes(sid)
    over_rounds = present - max_rounds if max_rounds > 0 else 0
    over_bytes = nbytes - max_bytes if max_bytes > 0 else 0
    if over_rounds <= 0 and over_bytes <= 0:
        return {}                                        # O(1) 门控：绝大多数轮次到此为止

    stored = sessions.get_history(sid, member_id)
    if not stored:
        return {}
    spans = sessions.round_spans(stored)
    base = store.session_trimmed_rounds(sid)
    summ = store.session_summary_rounds(sid)
    deletable = max(0, summ - base)                      # [base, summ) 才是"已覆盖"的可删前缀
    if deletable <= 0:
        logger.info("会话超上限但暂无可安全裁剪的轮（尚未被摘要覆盖）sid=%s 轮=%d 字节=%d",
                    sid, present, nbytes)
        return {"blocked": True, "rounds": present, "bytes": nbytes}

    need = max(0, over_rounds)
    if over_bytes > 0 and present > 0:
        avg = nbytes / present                           # 按均值折算"要删几轮才够"
        need = max(need, int(over_bytes / max(avg, 1)) + 1)
    n = min(deletable, max(1, need))
    remove_to = spans[n - 1][1]                          # 删掉 [0, remove_to) 条消息
    covered_by = sorted(i for i, m in store.load_summary_index(sid).items()
                        if m.get("rTo", 0) > base)
    store.trim_oldest_messages(sid, remove_to, trimmed_rounds_delta=n)
    audit = {
        "trimmedRounds": n, "trimmedMessages": remove_to,
        "fromRound": base, "toRound": base + n,
        "coveredBy": covered_by, "rounds": present, "bytes": nbytes,
        "ts": int(time.time()),
    }
    store.save_retention(sid, audit)
    logger.info("会话上限裁剪：sid=%s 删除绝对第 %d~%d 轮（%d 条消息），摘要段 %s 兜底",
                sid, base, base + n, remove_to, covered_by)
    return audit


# ---------------------------------------------------------------- 压缩（可同步调用）


def run_once(sid: str, member_id=None) -> int:
    """同步压一轮（后台线程 / 测试用），返回新压成的段数。

    幂等：已覆盖的段槽不重压；**某一段压缩失败即停止**（不跳过）——
    这样"已摘要轮数"始终是**前缀**，门控与 `summRounds` 才可信。
    """
    stored = sessions.get_history(sid, member_id)
    if not stored:
        return 0

    base = store.session_trimmed_rounds(sid)                 # 头部已被上限裁剪的轮数
    spans = sessions.round_spans(stored)                     # spans[k] = 绝对第 (base+k) 轮
    total = base + len(spans)                                # 绝对总轮数
    store.set_session_rounds(sid, total)                     # 回填/校正会话轮数

    seg_rounds = max(1, config.SUMMARY_SEG_ROUNDS)
    safe = max(0, total - sessions.HOT_ROUNDS)               # 热区不压
    complete = safe // seg_rounds                            # 能凑满几段

    index = store.load_summary_index(sid)
    made = 0
    for i in range(complete):
        if made >= config.SUMMARY_MAX_NEW_SEGS:
            break
        r_from, r_to = i * seg_rounds, (i + 1) * seg_rounds   # **绝对**轮号
        if _covered(index, r_from, r_to):
            continue                                         # 已被（可能是滚压出的）段覆盖
        k_from, k_to = r_from - base, r_to - base
        if k_from < 0 or k_to > len(spans):
            break                                            # 源轮不在库（异常）→ 停，保前缀性
        text = _compress(stored[spans[k_from][0]:spans[k_to - 1][1]])
        if text is None:
            break                                            # 失败即停：不留空洞
        seg_id = _save(sid, stored, base, r_from, r_to, text, level=1)
        index[seg_id] = {"rFrom": r_from, "rTo": r_to}
        made += 1

    if made:
        _rollup(sid, stored, base)
    return made


def _rollup(sid: str, stored, base: int) -> None:
    """段数超过阈值 → 把最旧的若干段滚压成一段（分段链上层），循环直到不超。"""
    while True:
        index = store.load_summary_index(sid)
        if len(index) <= config.SUMMARY_ROLLUP_SEGS:
            return
        ids = sorted(index)[:config.SUMMARY_ROLLUP_SEGS]
        segs = [s for s in (store.load_segment(sid, i) for i in ids) if s]
        if len(segs) < 2:
            return
        text = _compress_texts([s.get("text", "") for s in segs])
        if text is None:
            return                                           # 失败 → 保持原样（不丢数据）
        r_from = min(s["rFrom"] for s in segs)
        r_to = max(s["rTo"] for s in segs)
        level = max(int(s.get("level", 1)) for s in segs) + 1
        _save(sid, stored, base, r_from, r_to, text, level=level)
        for i in ids:
            store.delete_segment(sid, i)


def _save(sid: str, stored, base: int, r_from: int, r_to: int, text: str, level: int) -> int:
    """落一个摘要段并推进覆盖进度。返回段号。

    digest 由**轮区间**反推当前消息区间后计算；若该区间已不在库（被上限裁剪），
    记 `pruned=True` 且 digest 置空——装配侧据此直接信任它（它是唯一记录）。
    于是段记录里的 `mFrom/mTo` 只是调试信息、不参与校验，裁剪也就**无需改写任何段**。
    """
    index = store.load_summary_index(sid)
    seg_id = (max(index) + 1) if index else 0
    spans = sessions.round_spans(stored)
    k_from, k_to = r_from - base, r_to - base
    if 0 <= k_from and k_from < k_to <= len(spans):
        m_from, m_to = spans[k_from][0], spans[k_to - 1][1]
        digest = sessions.digest_msg(stored[m_from:m_to])
        pruned = False
    else:
        m_from = m_to = -1
        digest = ""
        pruned = True
    store.save_segment(sid, seg_id, {
        "seg": seg_id, "level": level,
        "rFrom": r_from, "rTo": r_to, "mFrom": m_from, "mTo": m_to,
        "digest": digest, "pruned": pruned, "text": text, "ts": int(time.time()),
    })
    # 覆盖进度按"前缀"推进（我们是从第 0 段顺序压的）
    store.set_session_summary_rounds(sid, max(store.session_summary_rounds(sid), r_to))
    return seg_id


def _covered(index: dict, r_from: int, r_to: int) -> bool:
    """这一段轮区间是否已被现有段覆盖（含被更大的滚压段包含）。"""
    return any(s.get("rFrom", -1) <= r_from and r_to <= s.get("rTo", -1)
               for s in index.values())


# ---------------------------------------------------------------- 调 LLM 压缩


def _compress(messages) -> str | None:
    """把一段消息压成要点；失败返回 None（调用方据此不写索引）。"""
    transcript = _render(messages)
    if not transcript.strip():
        return None
    return _ask(SUMMARY_SYSTEM_PROMPT, transcript, "seg")


def _compress_texts(texts) -> str | None:
    joined = "；".join(t for t in texts if t)
    if not joined.strip():
        return None
    return _ask(SUMMARY_ROLLUP_PROMPT, joined, "rollup")


def _ask(system: str, user: str, tag: str) -> str | None:
    """调一次 deepseek-chat。**所有异常都吞掉返回 None**——压缩是尽力而为，绝不能
    让它的失败影响对话（这是"可回滚"的实现前提）。"""
    try:
        llm = get_llm(temperature=0.2)
        msg = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        out = (msg.content or "").strip()
    except Exception as e:                                    # noqa: BLE001
        logger.warning("摘要压缩失败（%s）：%s", tag, e)
        return None
    if not out:
        logger.warning("摘要压缩返回空（%s）", tag)
        return None
    return out


def _render(messages) -> str:
    """把消息列表渲染成可读转录（供压缩器读）。工具 JSON 截断，只留要点。"""
    role_map = {"human": "用户", "ai": "助手", "tool": "工具返回", "system": "系统"}
    lines = []
    for m in messages:
        t = getattr(m, "type", None)
        role = role_map.get(t, t or "?")
        c = m.content if isinstance(m.content, str) else json.dumps(m.content, ensure_ascii=False)
        c = (c or "").strip()
        if len(c) > _RENDER_LIMIT:
            c = c[:_RENDER_LIMIT] + f"…（略 {len(c) - _RENDER_LIMIT} 字）"
        lines.append(f"{role}：{c}")
    return "\n".join(lines)
