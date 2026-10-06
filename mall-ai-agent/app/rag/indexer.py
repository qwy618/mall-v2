"""索引构建：把 mall-portal 的商品与评价抽成向量文档，写入 Qdrant。

**只经 REST 读 portal，不碰 DB、不碰 ES**（架构边界，见 docs/M3 §3.3）。
用到的 5 个接口全部是公开只读接口（无需登录）：
    GET /category/list               分类树（两级）
    GET /brand/list                  品牌表
    GET /product/list                商品分页（可 keyword/categoryId/brandId）
    GET /product/{id}                商品详情（product + skus）
    GET /comment/product/{id}        已审核评价分页

⚠️ **两处 portal 的形态限制（实测，与设计文档初稿不符，已回写 §2.4）**：
  1. `ProductVO` 只暴露 `id/productSn/name/pic/sale/status/lowestPrice` ——
     **没有 subTitle / categoryId / brandId**。因此：
       · 商品文本只能用 `name`（本项目 name 已把卖点拼进去了）；
       · 分类/品牌的归属改由**服务端过滤反推**（`?categoryId=` / `?brandId=` 是精确 eq），
         见 `_derive_category_map` / `_derive_brand_map`。
  2. `/product/list` 在**无 keyword 的 DB 分支不做 status 过滤**（实测 38 条含 7 条未上架）
     → 索引器**必须客户端复核 `status == 1`**。（有 keyword 时走 ES，那边过滤了 status=1。）

幂等：point id 用 uuid5(namespace, "product:{id}" / "review:{id}")，
重复索引是 upsert 覆盖，不产生重复文档，也不需要先删后建。
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid

from .. import config, store
from ..tools import mall_client
from . import aggregate, embedder, vector_store

log = logging.getLogger(__name__)

# 固定命名空间：写死以免换机器导致 id 变化（id 变了就会产生重复文档）
NS = uuid.UUID("6f1a4d2e-0000-4000-8000-6d616c6c7632")

INDEX_VERSION = "m3-1"          # 索引逻辑版本；改动文档组装方式时递增（便于追踪）

_SKIP_RE = re.compile(config.RAG_SKIP_NAME_PATTERN, re.I)


def pid_product(product_id) -> str:
    return str(uuid.uuid5(NS, f"product:{product_id}"))


def pid_review(product_id) -> str:
    return str(uuid.uuid5(NS, f"review:{product_id}"))


# ---------------------------------------------------------------- 数据抓取

def _data(body) -> object:
    """拆 CommonResult 信封，拿 data。"""
    return (body or {}).get("data")


def _pages(path: str, params: dict | None = None, page_size: int = 50,
           max_pages: int = 50) -> list[dict]:
    """按 pageNum 翻页拉列表接口，返回合并后的 list（自动跟随 total）。"""
    out: list[dict] = []
    page = 1
    while page <= max_pages:
        p = dict(params or {})
        p.update({"pageNum": page, "pageSize": page_size})
        d = _data(mall_client.api_get(config.PORTAL_BASE_URL, path, params=p)) or {}
        items = d.get("list") or []
        out.extend(items)
        total = int(d.get("total") or 0)
        if len(out) >= total or not items:
            break
        page += 1
    return out


def fetch_category_names() -> dict[int, str]:
    """分类树（两级）→ {id: name}。顶级与叶子都收，因为商品可能挂在任一级。"""
    nodes = _data(mall_client.api_get(config.PORTAL_BASE_URL, "/category/list")) or []
    names: dict[int, str] = {}

    def walk(items):
        for n in items or []:
            names[int(n["id"])] = n.get("name") or ""
            walk(n.get("children"))

    walk(nodes)
    return names


def fetch_brand_names() -> dict[int, str]:
    brands = _data(mall_client.api_get(config.PORTAL_BASE_URL, "/brand/list")) or []
    return {int(b["id"]): (b.get("name") or "") for b in brands}


def fetch_products() -> list[dict]:
    """全部商品（客户端复核 status==1 + 名称脏数据过滤）。"""
    raw = _pages("/product/list", page_size=50)
    kept, filtered = [], 0
    for p in raw:
        name = (p.get("name") or "").strip()
        if int(p.get("status") or 0) != 1:
            filtered += 1
            continue
        if _SKIP_RE.match(name):
            filtered += 1
            log.info("跳过脏数据商品 id=%s name=%r", p.get("id"), name)
            continue
        kept.append(p)
    log.info("商品：拉取 %s 条，保留 %s 条，过滤 %s 条", len(raw), len(kept), filtered)
    return kept


def _derive_category_map(category_ids: list[int]) -> dict[int, int]:
    """反推 商品 → 分类：`/product/list?categoryId=X` 是精确 eq 过滤。

    portal 不暴露 categoryId，只能这样反查；38 个分类 = 38 次 HTTP，秒级。
    同一商品若命中多个分类（不该发生），后写的覆盖（精确 eq 下不会发生）。
    """
    mapping: dict[int, int] = {}
    for cid in category_ids:
        try:
            for p in _pages("/product/list", {"categoryId": cid}, page_size=100):
                mapping[int(p["id"])] = cid
        except Exception as e:  # noqa: BLE001 —— 单个分类失败不该中断整个索引
            log.warning("分类 %s 反查失败：%s", cid, e)
    return mapping


def _derive_brand_map(brand_ids: list[int]) -> dict[int, int]:
    """反推 商品 → 品牌（同上）。"""
    mapping: dict[int, int] = {}
    for bid in brand_ids:
        try:
            for p in _pages("/product/list", {"brandId": bid}, page_size=100):
                mapping[int(p["id"])] = bid
        except Exception as e:  # noqa: BLE001
            log.warning("品牌 %s 反查失败：%s", bid, e)
    return mapping


def fetch_detail(product_id: int) -> dict:
    """商品详情 → {product, skus}。"""
    return _data(mall_client.api_get(config.PORTAL_BASE_URL,
                                     f"/product/{product_id}")) or {}


def fetch_reviews(product_id: int) -> list[dict]:
    """该商品的**已审核**评价（接口已保证只返回 status=1）。"""
    return _pages(f"/comment/product/{product_id}", page_size=50)


def _specs_of(skus: list[dict]) -> list[str]:
    """汇总 SKU 规格：spData 是 JSON 数组 [{"key":..,"value":..}]，去重保序。

    ⚠️ 禁 `Object.entries` 那类误用（前端踩过）；这里直接按 key/value 拼。
    只取规格文字，**丢弃 price / stock / lockStock**（红线，见 §4.4）。
    """
    seen: list[str] = []
    for s in skus or []:
        raw = s.get("spData")
        if not raw:
            continue
        try:
            arr = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(arr, list):
            continue
        parts = [f"{x.get('key')}:{x.get('value')}" for x in arr
                 if isinstance(x, dict) and x.get("key") and x.get("value")]
        spec = " ".join(parts)
        if spec and spec not in seen:
            seen.append(spec)
    return seen


# ---------------------------------------------------------------- 文档组装

def build_product_doc(product: dict, category_name: str, brand_name: str,
                      specs: list[str], now: int) -> dict:
    """商品档案文档。text 是**唯一被 embedding 的字段**，人可读、可复核。

    不含 price / stock / pic / productSn —— 前两者是快照（红线），
    后两者对语义检索无价值（且 productSn 是内部标识）。
    """
    name = (product.get("name") or "").strip()
    seg = [f"商品：{name}"]
    if category_name:
        seg.append(f"分类：{category_name}")
    if brand_name:
        seg.append(f"品牌：{brand_name}")
    if specs:
        seg.append("可选规格：" + "；".join(specs))
    text = "。".join(seg) + "。"

    return {
        "id": pid_product(product["id"]),
        "text": text,
        "payload": {
            "docType": "product_profile",
            "productId": int(product["id"]),
            "name": name,
            "categoryId": int(product.get("categoryId") or 0),
            "categoryName": category_name or "",
            "brandId": int(product.get("brandId") or 0),
            "brandName": brand_name or "",
            "skuSpecs": specs,
            "sale": int(product.get("sale") or 0),
            "indexedAt": now,
        },
    }


def build_review_doc(product: dict, category_id: int, reviews: list[dict],
                     agg: dict, now: int) -> dict:
    """口碑文档（评价聚合）。text = 标题行 + LLM 概述。

    **不把 pros/cons 再拼一遍**：它们与 LLM 概述是同一批信息（概述本就是对着它们写的），
    重复拼接会稀释 embedding 信号、也让注入给模型的 snippet 啰嗦。
    pros/cons/quotes 保留在 payload 里（供 tools 结构化使用/前端展示）。
    仅当 LLM 没给出概述时，才用结构化字段拼一份兜底文本。
    """
    stats = aggregate.star_stats(reviews)
    name = (product.get("name") or "").strip()
    head = f"商品：{name}。{stats['reviewCount']} 条评价，平均 {stats['starAvg']} 分"

    body = (agg.get("text") or "").strip()
    if not body:
        seg = []
        if agg.get("pros"):
            seg.append("好评集中在：" + "；".join(agg["pros"]))
        if agg.get("cons"):
            seg.append("槽点集中在：" + "；".join(agg["cons"]))
        if agg.get("quotes"):
            seg.append("用户原话：" + "；".join(agg["quotes"]))
        body = "。".join(seg) if seg else "暂无可用评价内容。"

    text = f"{head}。{body}"

    return {
        "id": pid_review(product["id"]),
        "text": text,
        "payload": {
            "docType": "review_summary",
            "productId": int(product["id"]),
            "name": name,
            "categoryId": int(category_id or 0),
            "starAvg": float(stats["starAvg"]),
            "starDist": stats["starDist"],
            "reviewCount": int(stats["reviewCount"]),
            "pros": agg.get("pros") or [],
            "cons": agg.get("cons") or [],
            "quotes": agg.get("quotes") or [],
            "indexedAt": now,
        },
    }


# ---------------------------------------------------------------- 主流程

def build(force: bool = False, only_product: int | None = None,
          with_reviews: bool = True) -> dict:
    """构建索引（全量 or 单商品）。

    force=True → 重建 collection（换 embedding 模型/维度、或索引损坏时用）。
    only_product=N → 只刷该商品（增量单刷，不做陈旧清理）。
    """
    t0 = time.time()
    now = int(t0)

    vector_store.ensure_collection(force=force)

    cat_names = fetch_category_names()
    brand_names = fetch_brand_names()
    products = fetch_products()
    if only_product is not None:
        products = [p for p in products if int(p["id"]) == only_product]

    # 反推归属（仅在需要时做，单商品刷新时也做，保证 payload 完整）
    cat_map = _derive_category_map(sorted(cat_names.keys()))
    brand_map = _derive_brand_map(sorted(brand_names.keys()))

    docs: list[dict] = []
    err = 0
    review_products = 0

    for p in products:
        pid = int(p["id"])
        cid = cat_map.get(pid, 0)
        bid = brand_map.get(pid, 0)
        # 把反推结果并进 product，供文档组装使用
        p = {**p, "categoryId": cid, "brandId": bid}

        try:
            detail = fetch_detail(pid)
            skus = detail.get("skus") or []
        except Exception as e:  # noqa: BLE001
            log.warning("详情抓取失败 id=%s：%s", pid, e)
            skus = []
            err += 1

        docs.append(build_product_doc(p, cat_names.get(cid, ""),
                                      brand_names.get(bid, ""),
                                      _specs_of(skus), now))

        if not with_reviews:
            continue

        try:
            reviews = fetch_reviews(pid)
        except Exception as e:  # noqa: BLE001
            log.warning("评价抓取失败 id=%s：%s", pid, e)
            reviews = []
            err += 1

        if len(reviews) >= config.RAG_MIN_REVIEWS:
            try:
                agg = aggregate.aggregate_reviews(p["name"], "", reviews)
            except Exception as e:  # noqa: BLE001 —— 聚合失败就退化为"无功无过"的空文档
                log.warning("评价聚合失败 id=%s：%s", pid, e)
                agg = {"pros": [], "cons": [], "quotes": [], "text": ""}
                err += 1
            docs.append(build_review_doc(p, cid, reviews, agg, now))
            review_products += 1

    # 批量 embed（分批，避免一次性喂太多）
    texts = [d["text"] for d in docs]
    vectors: list[list[float]] = []
    for i in range(0, len(texts), config.RAG_INDEX_BATCH):
        vectors.extend(embedder.embed_documents(texts[i:i + config.RAG_INDEX_BATCH]))
    for d, v in zip(docs, vectors):
        d["vector"] = v

    written = vector_store.upsert(docs)

    # 陈旧清理：Qdrant 里存在、但本次未再见到的商品 → 说明已下架/删除
    removed = 0
    if only_product is None:
        live = {int(d["payload"]["productId"]) for d in docs}
        stale = [p["id"] for p in vector_store.scroll_all()
                 if int((p["payload"] or {}).get("productId") or 0) not in live]
        removed = vector_store.delete_ids(stale)

    meta = {
        "lastIndexedAt": now,
        "docCount": written,
        "productProfileCount": len(docs) - review_products,
        "reviewSummaryCount": review_products,
        "embedModel": config.EMBED_MODEL,
        "embedDim": config.EMBED_DIM,
        "indexVersion": INDEX_VERSION,
        "filteredCount": 0,
        "errorCount": err,
    }
    store.save_rag_meta(meta)

    return {
        "ok": True,
        "products": len(products),
        "docs": written,
        "removedStale": removed,
        "errors": err,
        "elapsed": round(time.time() - t0, 1),
        "meta": meta,
    }


def build_with_lock(force: bool = False, only_product: int | None = None) -> dict:
    """带单飞锁的构建入口（定时任务 / 启动自建走这里）。

    多 worker 下只有一个实例真正跑；抢不到锁返回 skipped=True（不是错误）。
    """
    token = uuid.uuid4().hex
    if not store.acquire_rag_lock(token):
        return {"ok": True, "skipped": True,
                "reason": "另一个实例正在构建索引（ai:rag:lock 被持有）"}
    try:
        return build(force=force, only_product=only_product)
    finally:
        store.release_rag_lock(token)


def index_status() -> dict:
    """索引自检：把「Qdrant 实况」与「Redis 元数据」对账，回答"要不要重建"。

    调用方：定时任务的启动自检（M3.3）、`rag_reindex.py --check`、验收脚本。
    判定为"索引失效"的四种情形（docs §5.4）：
      · 向量库不可达 / collection 不存在  → 必须建
      · 维度不符（换过 embedding 模型）    → 必须 force 重建（维度不可变）
      · meta 缺失（首次部署 / Redis 被清） → 建
      · docCount 与实况不符（索引被外部改动 / 上次构建中断）→ 重建
    索引时间只给运维看，**绝不向用户暴露**（M3 §5.4）。
    """
    sh = vector_store.health()
    meta = store.load_rag_meta()
    reasons: list[str] = []

    if not sh.get("ok"):
        reasons.append(f"向量库不可达（{sh.get('error')}）")
    elif not sh.get("exists"):
        reasons.append("collection 尚未创建")
    elif not sh.get("consistent"):
        reasons.append(f"维度不符（库内 {sh.get('dim')} != EMBED_DIM {config.EMBED_DIM}）")

    if not meta:
        reasons.append("索引元数据缺失（ai:rag:meta）")
    else:
        if meta.get("embedModel") != config.EMBED_MODEL:
            reasons.append(f"embedding 模型已变（{meta.get('embedModel')} → {config.EMBED_MODEL}）")
        if int(meta.get("embedDim") or 0) != config.EMBED_DIM:
            reasons.append(f"embedding 维度已变（{meta.get('embedDim')} → {config.EMBED_DIM}）")
        actual = sh.get("points") or 0
        if int(meta.get("docCount") or 0) != actual:
            reasons.append(f"文档数不符（meta {meta.get('docCount')} vs 实况 {actual}）")

    # 维度类问题必须 force（否则 ensure_collection 之外的写入会维度不匹配）
    need_force = any("维度" in r for r in reasons)

    return {
        "ok": not reasons,
        "reasons": reasons,
        "needForce": need_force,
        "points": sh.get("points"),
        "dim": sh.get("dim"),
        "collectionExists": bool(sh.get("exists")),
        "qdrantOk": bool(sh.get("ok")),
        "meta": meta,
    }


def detail(product_id: int) -> dict:
    """单商品重建（`--product N`）。"""
    return build(only_product=product_id)
