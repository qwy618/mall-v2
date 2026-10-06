"""文本向量化 —— RAG 的唯一 embedding 入口。

**为什么不用 DeepSeek**：DeepSeek 官方只提供 chat/completions，
**没有 embeddings 端点**（已核实），所以向量化必须外部解决。

**为什么默认 fastembed**：ONNX Runtime 推理，**不引 PyTorch**（省 ~2GB 依赖），
模型 `BAAI/bge-small-zh-v1.5` 只有 ~91MB、512 维、中文效果好。
实测：同题余弦 0.67 / 异题 0.31 —— 区分度足够支撑相似度阈值。

**为什么封成单一接口**：换 provider（如阿里云 DashScope text-embedding）只改本文件，
indexer / retriever 无感；`EMBED_MODEL + EMBED_DIM` 会写进索引元数据作为指纹，
一旦变动即触发 collection 重建（维度不可变）。
"""
import threading

from .. import config

_model = None
_lock = threading.Lock()


def _load():
    """惰性加载模型（进程内单例）。

    不用模块级立即初始化：import app.rag 时就去下 91MB 模型，
    会让"只想读个配置"的调用方也付下载代价。
    """
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:      # 双检：并发首调只加载一次
            return _model
        if config.EMBED_PROVIDER != "fastembed":
            raise NotImplementedError(
                f"EMBED_PROVIDER={config.EMBED_PROVIDER} 尚未实现。"
                "接第三方时在此分支调用其 embeddings 接口并返回等长向量即可。"
            )
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name=config.EMBED_MODEL,
                               cache_dir=config.EMBED_CACHE_DIR)
    return _model


def embed_documents(texts: list[str]) -> list[list[float]]:
    """批量向量化文档（建索引用）。返回与入参等长的向量列表。"""
    if not texts:
        return []
    model = _load()
    return [list(v) for v in model.embed(texts)]


def embed_query(text: str) -> list[float]:
    """向量化一条检索 query。

    与文档侧**分开调用**是有意的：bge 系列模型对 query 会加检索指令前缀
    （fastembed 的 query_embed 负责），文档侧不加 —— 用错一侧会明显掉分。
    """
    model = _load()
    fn = getattr(model, "query_embed", None)
    if fn is not None:
        return list(next(iter(fn([text]))))
    return list(next(iter(model.embed([text]))))


def dim() -> int:
    """当前模型的向量维度（用于与 collection / 索引元数据比对指纹）。"""
    return config.EMBED_DIM
