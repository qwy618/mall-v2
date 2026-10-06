"""Qdrant 封装 —— RAG 的向量库边界（全项目**唯一** import qdrant_client 的地方）。

**为什么是 server 模式**：M1 已确立硬指标"worker 数 1→2 功能行为必须不变"。
Chroma 之类的进程内/本地文件型向量库，每个 worker 各存一份索引 →
"刚写入的向量另一个进程查不到"，这与 M1 前的模块级 dict 是同一种病。
Qdrant 独立进程对外提供网络接口，多 worker 查同一份数据，天然跨进程。

**为什么不直连 mall 的 ES**：ES 是 mall-portal 的内部实现（`EsProductService`）。
助手只经 REST 调 portal 是一条架构边界，直连 ES 等于把 portal 的私有存储
当成助手的公开依赖 —— 以后 portal 换检索实现就会把助手带崩。

**维度不可变**：Qdrant collection 的向量维度创建后不能改。`ensure_collection`
把当前 `EMBED_DIM` 与 collection 现状比对，不符即**直接重建**（幂等 id + 全量
重建的成本极低，见 docs/M3 §5.5）。
"""
from __future__ import annotations

import logging

from qdrant_client import QdrantClient, models

from .. import config

log = logging.getLogger(__name__)

_client: QdrantClient | None = None

# payload 里用于预过滤 / 回填的字段（见 docs/M3 §4.6）
#   keyword 走精确匹配；integer 用于范围/集合过滤
_PAYLOAD_INDEXES: dict[str, models.PayloadSchemaType] = {
    "docType": models.PayloadSchemaType.KEYWORD,
    "categoryId": models.PayloadSchemaType.INTEGER,
    "brandId": models.PayloadSchemaType.INTEGER,
}


def client() -> QdrantClient:
    """进程内单例客户端（连接池线程安全，与 store.client 同风格）。"""
    global _client
    if _client is None:
        _client = QdrantClient(url=config.QDRANT_URL,
                               api_key=config.QDRANT_API_KEY or None,
                               timeout=30)
    return _client


def collection_dim(name: str | None = None) -> int | None:
    """读取现有 collection 的向量维度；不存在/不可读返回 None。

    公开（非 `_` 前缀）：启动自检 / `--check` / 验收脚本要拿它跟 `EMBED_DIM` 比对，
    判断"索引是否因换模型/换维度而失效"（docs §5.4 指纹规则）。
    """
    try:
        info = client().get_collection(name or config.RAG_COLLECTION)
    except Exception:  # noqa: BLE001 —— 不存在、网络抖动都算"读不到"
        return None
    vectors = info.config.params.vectors
    # 命名向量会返回 dict；本项目用默认单向量
    return getattr(vectors, "size", None)


def ensure_collection(force: bool = False) -> None:
    """确保 collection 存在且维度正确；维度不符则重建。

    `force=True` 用于"换 embedding 模型/维度"或 collection 损坏。
    """
    name = config.RAG_COLLECTION
    existing = collection_dim(name)

    if existing is not None and existing != config.EMBED_DIM:
        log.warning("collection %s 维度 %s != EMBED_DIM %s → 重建",
                    name, existing, config.EMBED_DIM)
        force = True

    if force and existing is not None:
        client().delete_collection(name)
        existing = None

    if existing is None:
        client().create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=config.EMBED_DIM,
                                               distance=models.Distance.COSINE),
        )
        for field, schema in _PAYLOAD_INDEXES.items():
            client().create_payload_index(collection_name=name,
                                          field_name=field,
                                          field_schema=schema)
        log.info("collection %s 已创建（dim=%s, cosine）", name, config.EMBED_DIM)


def drop() -> None:
    """删除整个 collection（全量重建前用；数据可由 portal REST 无损重建）。"""
    try:
        client().delete_collection(config.RAG_COLLECTION)
    except Exception:  # noqa: BLE001 —— 不存在即目标状态
        pass


def upsert(docs: list[dict]) -> int:
    """按 uuid5 幂等写入（同 id 覆盖，不产生重复文档）。

    docs 每项：{id: str(uuid), vector: list[float], payload: dict, text: str}
    `text` 落到 payload.text（人可读、可复核、可回填 snippet）。
    """
    if not docs:
        return 0
    points = [
        models.PointStruct(
            id=d["id"],
            vector=d["vector"],
            payload={**d["payload"], "text": d.get("text", "")},
        )
        for d in docs
    ]
    client().upsert(collection_name=config.RAG_COLLECTION, points=points, wait=True)
    return len(points)


def _build_filter(doc_types: list[str] | None,
                  product_ids: list[int] | None,
                  category_id: int | None) -> models.Filter | None:
    must: list[models.Condition] = []
    if doc_types:
        must.append(models.FieldCondition(key="docType",
                                         match=models.MatchAny(any=doc_types)))
    if product_ids:
        must.append(models.FieldCondition(key="productId",
                                         match=models.MatchAny(any=list(product_ids))))
    if category_id is not None:
        must.append(models.FieldCondition(key="categoryId",
                                         match=models.MatchValue(value=category_id)))
    return models.Filter(must=must) if must else None


def search(vector: list[float], *, limit: int,
           doc_types: list[str] | None = None,
           product_ids: list[int] | None = None,
           category_id: int | None = None) -> list[dict]:
    """向量检索，返回 [{id, score, payload}]，按相似度降序。

    `doc_types` 默认按调用方给的值（retriever 传两类都收）。
    用 `query_points`（1.16+ 的推荐 API）而非已废弃的 `search`。
    """
    qfilter = _build_filter(doc_types, product_ids, category_id)
    res = client().query_points(
        collection_name=config.RAG_COLLECTION,
        query=vector,
        query_filter=qfilter,
        limit=limit,
        with_payload=True,
    )
    out: list[dict] = []
    for p in res.points:
        out.append({"id": str(p.id), "score": float(p.score), "payload": p.payload or {}})
    return out


def count() -> int:
    """collection 内文档总数（运维/验收用）。"""
    try:
        return int(client().count(config.RAG_COLLECTION, exact=True).count)
    except Exception:  # noqa: BLE001
        return 0


def scroll_all(with_vectors: bool = False) -> list[dict]:
    """遍历全部 point（仅用于"清理本次未再见到的旧文档"这类维护动作）。"""
    out: list[dict] = []
    offset = None
    while True:
        points, offset = client().scroll(
            collection_name=config.RAG_COLLECTION,
            limit=256, offset=offset,
            with_payload=True, with_vectors=with_vectors,
        )
        out.extend({"id": str(p.id), "payload": p.payload or {}} for p in points)
        if offset is None:
            break
    return out


def delete_ids(ids: list[str]) -> int:
    """按 point id 删除（清理陈旧文档）。"""
    if not ids:
        return 0
    client().delete(collection_name=config.RAG_COLLECTION,
                    points_selector=models.PointIdsList(points=list(ids)), wait=True)
    return len(ids)


def health() -> dict:
    """连通性与指纹信息（`--check` 用；不抛异常）。

    区分三种状态，否则"没建过索引"会被误报成"连不上 Qdrant"：
      ok=False                → 连不上服务（URL/网络/容器没起）
      ok=True, exists=False   → 连得上，但 collection 还没建（首次部署的正常状态）
      ok=True, exists=True    → 正常，附 points/dim/consistent
    """
    base = {"url": config.QDRANT_URL, "collection": config.RAG_COLLECTION}
    try:
        client().get_collections()          # 探活：能不能连上
    except Exception as e:  # noqa: BLE001
        return {**base, "ok": False, "exists": False, "error": str(e)}

    try:
        info = client().get_collection(config.RAG_COLLECTION)
    except Exception:  # noqa: BLE001 —— 连得上但 collection 不存在
        return {**base, "ok": True, "exists": False, "points": 0,
                "dim": None, "expectedDim": config.EMBED_DIM, "consistent": False}

    vectors = info.config.params.vectors
    size = getattr(vectors, "size", None)
    return {
        **base,
        "ok": True,
        "exists": True,
        "points": int(info.points_count or 0),
        "dim": size,
        "expectedDim": config.EMBED_DIM,
        "consistent": size == config.EMBED_DIM,
    }
