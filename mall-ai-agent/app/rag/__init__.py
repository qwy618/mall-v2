"""RAG 检索增强（M3）。

分工铁律（见 docs/M3_RAG检索增强设计.md）：
  - **结构类**问题（价格 / 库存 / 规格 / 有没有货）→ 走工具实时查 mall-portal；
  - **语义类**问题（口碑 / 手感 / 适用场景）→ 走本模块的向量检索。

因此向量库里**永不出现价格与库存**：它们是快照，进了索引就会过期，
检索到过期价再复述给用户 = 幻觉。红线由 app/rag/aggregate.py（生成侧清洗）
+ app/rag/indexer.py（字段排除）+ 验收脚本（断言）三重保证。

模块划分：
  embedder.py      文本 → 向量（fastembed / ONNX，不依赖 PyTorch）
  vector_store.py  Qdrant 封装（server 模式，跨 worker 共享）
  aggregate.py     评价 → 口碑文档（LLM，本模块唯一的"创作"点）
  indexer.py       全量/单商品构建，uuid5 幂等 upsert
  retriever.py     检索 + L1 拒答闸门

对外只暴露一个入口给工具层：
"""
from .retriever import search_knowledge_impl

__all__ = ["search_knowledge_impl"]
