# mall-ai-agent

mall-v2 商城的 AI 购物助手：对话找货、商品详情、购物车、下单、猜你喜欢，后续接入 RAG 知识问答。
定位为商城的**第 4 个服务**（Python），只通过 REST API 调用 `mall-portal`，不改任何 Java 业务代码。

> 生产化设计（工具映射总表、状态外置、下单同源试算、RAG、治理、M0→M4 里程碑）见
> [`docs/智能助手生产化设计.md`](docs/智能助手生产化设计.md)。

## 架构

```
portal-web(C 端商城) --HTTP/SSE--> AI Agent 服务(FastAPI :8090)
                                      ├─ LangGraph 编排（ReAct 循环）
                                      ├─ Tools：搜索/详情/购物车/下单/推荐 → mall-portal(:8081)
                                      └─ 会话与草稿（M1 起 Redis；RAG 见 M3）
```

- LLM：DeepSeek（OpenAI 兼容模式）
- Agent 框架：LangChain + LangGraph（`create_react_agent`）
- 后端依赖：只有一个 —— `mall-portal`（**ES 已内置在 portal，没有独立搜索服务**）

## 快速开始

```bash
# 1. 配置（DeepSeek Key 可在 https://platform.deepseek.com 创建）
cp .env.example .env      # 填入 DEEPSEEK_API_KEY；PORTAL_BASE_URL 默认 http://localhost:8081

# 2. 安装依赖（已装过可跳过）
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 3. 确保 mall-portal 已在 8081 运行，然后命令行验证
.venv\Scripts\python scripts/cli_chat.py
# 试试问：帮我找小米手机   → 再来一句：加入购物车

# 4. 启动 HTTP 服务
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8090
```

## 目录结构

```
app/
├── main.py               # FastAPI 入口（/health、/api/chat、/api/chat/stream、/api/chat/history、/api/chat/clear）
├── agent.py              # Agent 组装（SYSTEM_PROMPT + 工具注册）
├── llm.py                # ChatOpenAI → DeepSeek 兼容模式
├── config.py             # .env 配置读取（含 M1.5 装配/摘要/上限阈值）
├── schemas.py            # 请求模型
├── store.py              # Redis 门面（M1）：会话事实源 / 草稿 / 结果回放 / 摘要段 / 上限裁剪
├── sessions.py           # 会话装配（M1.5）：T0–T3 分级降级 + token 精算 + 摘要校验注入
├── summarize.py          # T3 分段摘要链（M1.5.3）+ 单会话上限裁剪（M1.5.4）
├── prompts.py            # 摘要压缩提示词（只压缩、不引申）
├── orders.py             # 订单草稿业务封装
└── tools/
    ├── mall_client.py     # portal HTTP 客户端（body.code / 401 怪癖处理）
    ├── product_tools.py   # search_products / show_products / get_product_detail
    ├── order_tools.py     # add_to_cart / list_cart / preview_order / place_order
    └── recommend_tools.py # recommend_for_me（购物车+收藏 → 相似商品）
scripts/
├── cli_chat.py             # 命令行调试入口（交互）
├── smoke_p1.py             # 非交互冒烟（跑一次完整 ReAct 循环）
├── smoke_m0*.py            # M0 工具层对齐（直连 / 真实 LLM / 下单两段式）
├── smoke_m1_state.py       # M1 状态层（会话/草稿/结果回放/双实例续聊）
├── smoke_m1_*.py           # M1 试算同源 / 确认页推导
├── smoke_m15_state.py      # M1.5 存储迁移 + T0–T2 分级装配
├── smoke_m15_summary.py    # M1.5.3 分段摘要链 + 回滚（加 M15S_LLM=1 走真实 LLM）
├── smoke_m15_retention.py  # M1.5.4 上限裁剪 + token 精算
└── smoke_m15_e2e.py        # M1.5 端到端（真实 LLM，含 T3 注入）
```

## 工具 → mall-v2 接口映射

| 工具 | 方法 | mall-v2 端点 | 备注 |
|---|---|---|---|
| `search_products` | GET | `/product/list` | `keyword/categoryId/brandId/pageNum(从1)/pageSize`；有词走 ES，异常降级 DB |
| `get_product_detail` | GET | `/product/{id}` | 返回 `{product, skus}`；无属性表 |
| `add_to_cart` | POST | `/cart/add?skuId=&quantity=` | `@RequestParam`，快照由后端落库 |
| `list_cart` | GET | `/cart/list` | 字段 `cartItemId` / `skuId` |
| `preview_order` | POST | `/order/preview` | 与 `/order/create` **同源试算**（同一 `computeAmounts`），只算不落库 |
| `place_order` | POST | `/order/token` → `/order/create` | 必带 `submitToken`（一次性，TTL 900s） |
| `recommend_for_me` | GET | `/member/collect/list` + `/product/similar/{id}` | 购物车/收藏为种子召回相似商品 |

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| P0–P4 | 骨架、搜索/详情、SSE 流式、JWT 透传+加购下单+人工确认、猜你喜欢 | 已完成 |
| **M0** | **对接修复：工具层对齐 mall-v2 + 端口 8081 + 401 判定** | **已完成** |
| M1 | 状态外置 Redis；`/order/preview` 同源试算；`submitToken` 幂等与并发保护 | **M1.1–M1.5 全部完成**（M1.5 长会话装配：存储/装配分离 + T0–T3 分级降级 + 可回滚摘要链 + 单会话上限裁剪 + token 精算） |
| M2 | 前端嵌入 `portal-web`（悬浮球 + 抽屉 + SSE 解析 + 卡片渲染） | **已完成**（含 SSE `tool` 无结束信号导致的「假进行中」修复） |
| M3 | RAG（商品 + 评价知识库、引用、拒答） | **M3.0–M3.5 全部完成**（40 文档索引 · 引用卡片 · 定时增量 · 金标集回归 检索 25/25 · Agent 8/8） |
| M4 | 治理与可观测 | **进行中**：M4.1 治理层 ✅（限流 / 配额 / 成本上限 / 降级，51/51）· M4.2 安全加固 ✅（CORS 白名单 · 日志脱敏 · 注入声明，48/48）。待做：结构化日志与指标 · 业务类金标用例 · Langfuse |

## 关键约定

- portal 接口失败也常返回 **HTTP 200**，真实状态在 `body.code`；**未登录是 HTTP 401**——
  两者都在 `tools/mall_client.py` 统一处理（401 必须在 `raise_for_status()` 前判定，否则登录引导链路会断）
- 下单必须走人工确认卡片；支付由用户自己在商城完成
- C 端会员 JWT 由前端在请求体中传入，工具通过 ContextVar 透传 `Authorization: Bearer`
- 取图口径：卡片图直接用 portal 返回的 `pic`（portal 已按「SKU 图 → 商品图」回退）
