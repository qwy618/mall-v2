"""全局配置：全部从环境变量/.env 读取"""
import os

from dotenv import load_dotenv

load_dotenv()

# DeepSeek（OpenAI 兼容模式）
# Key 来源优先级：系统环境变量 DEEPSEEK_API_KEY > .env 文件
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# mall-v2 portal —— 助手唯一后端依赖（ES 已内置进 portal，无独立搜索服务）
PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "http://localhost:8081")

# 状态层（M1）：会话历史 / 订单草稿 / 幂等结果缓存
# 用 db5 与 portal 的 db0 物理隔离；键前缀统一 ai:（见 app/store.py）
# 生产/本机真实连接串（含密码）放 .env，不写这里
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/5")

# ---------------------------------------------------------------- 长对话装配（M1.5）
#
# 存储与装配分离：Redis 存**全量原文**（只追加、不因压缩而删），
# 每轮请求时按预算做分级降级装配（见 app/sessions.py 的 assemble_history）。
#
#   预算：装配出的 prompt 目标 token 数（软约束——宁可略超，也不能装配失败）
SESSION_TOKEN_BUDGET = int(os.getenv("SESSION_TOKEN_BUDGET", "6000"))
#   热区：最近 N 轮**永不压缩**（原文保留；T1 不桩化、T2 不折叠）
#        含未消费订单草稿的轮次也会被钉住，不受此限制
HOT_ROUNDS = int(os.getenv("HOT_ROUNDS", "6"))
#   头部保真：T2 折叠时额外保留最早的 N 轮（初始偏好 / 总目标常在最前）
HEAD_KEEP_ROUNDS = int(os.getenv("HEAD_KEEP_ROUNDS", "2"))

# ---------------- T3：LLM 分段摘要链（M1.5.3）----------------
#
# 只压"热区之外"的旧轮：每 SUMMARY_SEG_ROUNDS 轮压成一段，段数超阈值再滚压成更高层的段。
# 摘要是**派生缓存**（可丢可重算），原文永不因压缩而删；压缩在**后台线程**里做（惰性异步）。
SUMMARY_ENABLED = os.getenv("SUMMARY_ENABLED", "1").lower() not in ("0", "false", "no")
#   每段摘要覆盖的轮数（段粒度）
SUMMARY_SEG_ROUNDS = int(os.getenv("SUMMARY_SEG_ROUNDS", "8"))
#   未摘要轮数超过多少就触发异步压缩（惰性阈值；实际以"能否凑满一段"为准）
SUMMARY_TRIGGER_UNSUMMARIZED = int(os.getenv("SUMMARY_TRIGGER_UNSUMMARIZED", "16"))
#   段数超过此值 → 把最旧的若干段滚压成更高层的一段（分段链，防段数无限增长）
SUMMARY_ROLLUP_SEGS = int(os.getenv("SUMMARY_ROLLUP_SEGS", "12"))
#   单次后台任务最多新压几段（防长会话一次压太久，占用 LLM 配额）
SUMMARY_MAX_NEW_SEGS = int(os.getenv("SUMMARY_MAX_NEW_SEGS", "4"))
#   单飞锁 TTL（秒）：多 worker/多线程下防止同一会话被重复压缩
SUMMARY_LOCK_TTL = int(os.getenv("SUMMARY_LOCK_TTL", "90"))

# ---------------- M1.5.4：单会话上限（达上限才删最旧）----------------
SESSION_MAX_ROUNDS = int(os.getenv("SESSION_MAX_ROUNDS", "300"))
SESSION_MAX_BYTES = int(os.getenv("SESSION_MAX_BYTES", str(2 * 1024 * 1024)))
#   兼容旧配置名：语义已变（由"总条数上限"→"热区上限"），保留以免旧 .env 报错
SESSION_MAX_MESSAGES = int(os.getenv("SESSION_MAX_MESSAGES", "48"))

# ---------------------------------------------------------------- RAG（M3）
#
# 分工铁律：**结构类问题（价格/库存/规格/有没有货）走工具实时查，语义类问题
# （口碑/手感/适用场景）走 RAG**。所以向量库里永不出现价格/库存——快照必然过期，
# 检索到过期价即幻觉。详见 docs/M3_RAG检索增强设计.md §4.4。
#
# 开关：置 0 时 search_knowledge 直接返回"暂无信息"，用于一键回退（索引挂了也不影响其余工具）
RAG_ENABLED = os.getenv("RAG_ENABLED", "1").lower() not in ("0", "false", "no")

RAG_COLLECTION = os.getenv("RAG_COLLECTION", "mall_knowledge")
# Qdrant 走 server 模式（独立进程）：多 worker 查同一份数据，
# 不用"进程内/本地文件"型向量库（那会和 M1 前的内存 dict 一样各存一份 → 串会话）
#   默认指向中间件主机（与 Redis/RabbitMQ 同一台），容器名为 qdrant
QDRANT_URL = os.getenv("QDRANT_URL", "http://192.168.150.128:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

# Embedding：DeepSeek 只提供 chat/completions，没有 embeddings 端点 → 必须外部解决。
# fastembed 走 ONNX 运行时（不引 PyTorch，~91MB 模型），封在 embedder 单一接口后可切第三方。
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "fastembed")     # fastembed | dashscope
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-zh-v1.5")
EMBED_DIM = int(os.getenv("EMBED_DIM", "512"))
EMBED_CACHE_DIR = os.getenv("EMBED_CACHE_DIR", "./data/fastembed")

# 检索
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
#   阈值按 M3.5 金标集（28 条，19 正 / 6 越界）复标，见 eval/baseline.json：
#   越界样本最高 0.4560，正样本最低 0.5022 → 安全区间 (0.4560, 0.5022]，
#   取两侧最小余量最大化的中值 0.48（下 0.0240 / 上 0.0222）。
#   旧值 0.46 距越界样本仅 0.0040，一次 embedding 抖动就会漏放 → 已弃用。
#   🔴 注意：embedding 在本语料上区分度窄（两个边界只差 0.046），
#   阈值天然脆弱，真正的改善要靠换更好的 embedding 或开 rerank（docs/M3 §10 R5）。
RAG_SIM_THRESHOLD = float(os.getenv("RAG_SIM_THRESHOLD", "0.48"))
RAG_MAX_PER_PRODUCT = int(os.getenv("RAG_MAX_PER_PRODUCT", "1"))
RAG_FETCH_MULTIPLIER = int(os.getenv("RAG_FETCH_MULTIPLIER", "3"))
RAG_RERANK = os.getenv("RAG_RERANK", "0").lower() not in ("0", "false", "no")

# 索引
RAG_INDEX_CRON = os.getenv("RAG_INDEX_CRON", "0 3 * * *")
RAG_INDEX_ON_START = os.getenv("RAG_INDEX_ON_START", "0").lower() not in ("0", "false", "no")
#   生成 review_summary 所需的最少有效评价数
RAG_MIN_REVIEWS = int(os.getenv("RAG_MIN_REVIEWS", "1"))
RAG_AGG_MAX_INPUT_TOKENS = int(os.getenv("RAG_AGG_MAX_INPUT_TOKENS", "2000"))
RAG_INDEX_BATCH = int(os.getenv("RAG_INDEX_BATCH", "32"))
#   脏数据商品名（实测库里存在 "test"/"xxx"）——不进索引
RAG_SKIP_NAME_PATTERN = os.getenv("RAG_SKIP_NAME_PATTERN", r"^(test|xxx|\d+)$")
#   单飞锁 TTL（秒）：多 worker 下只允许一个实例真正重建
RAG_LOCK_TTL = int(os.getenv("RAG_LOCK_TTL", "300"))

# ---------------------------------------------------------------- 治理（M4）
#
# 三层防线，越靠前越"便宜"：
#   限流（分钟窗口）→ 挡瞬时刷量；配额（日窗口）→ 限总量；成本上限 → 保命
# 计数一律放 Redis（多 worker 共享）——进程内计数等于每个 worker 各算一份，形同虚设。
#
# 一键回退：置 0 后完全跳过治理检查（排查"是不是治理误伤"时用）
GUARD_ENABLED = os.getenv("GUARD_ENABLED", "1").lower() not in ("0", "false", "no")

#   限流：会员按 memberId；游客按 **IP**
#   —— 游客不能用 session_id 当身份：那是前端生成的，换一个就绕过了
RATE_PER_MIN_MEMBER = int(os.getenv("RATE_PER_MIN_MEMBER", "10"))
RATE_PER_MIN_GUEST = int(os.getenv("RATE_PER_MIN_GUEST", "5"))

#   配额：日累计。游客给得少（匿名流量最容易刷）
QUOTA_PER_DAY_MEMBER = int(os.getenv("QUOTA_PER_DAY_MEMBER", "100"))
QUOTA_PER_DAY_GUEST = int(os.getenv("QUOTA_PER_DAY_GUEST", "20"))

#   成本上限：**全站**日 token 总量（含所有用户）。超阈后新请求切到 fallback 模型；
#   fallback 未配置则当日停止对话（宁可拒答，不可烧穿预算）
DAILY_TOKEN_LIMIT = int(os.getenv("DAILY_TOKEN_LIMIT", "2000000"))
DEEPSEEK_FALLBACK_MODEL = os.getenv("DEEPSEEK_FALLBACK_MODEL", "")

#   LLM 超时：不设的话上游卡住会一直挂着，SSE 连接既不返回也不报错（最难排查的一种）
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
#   SDK 自动重试次数：默认 0——重试会放大 token 消耗；且用户已感到"卡住"，
#   与其默默重试不如直接告诉他稍后再试
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "0"))

#   计数键 TTL 冗余量（秒）：只需覆盖一个窗口，跨窗换 key 故不会互相污染
GUARD_KEY_TTL_SLACK = int(os.getenv("GUARD_KEY_TTL_SLACK", "90"))

# ---------------------------------------------------------------- 安全（M4.2）
# CORS 白名单：逗号分隔的完整源。默认只放行 portal-web 的两个开发端口。
# 置为 * 是**显式开发逃生口**（此时退回放开所有源）。
CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:3001,http://127.0.0.1:3001,"
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",") if o.strip()]

# 额外放行正则：开发期 Vite 端口会变、手机真机走局域网 IP 联调。
# 只放行 RFC1918 私网与本机回环，**不匹配任意公网域名**——收紧 CORS 的意义在于
# 拦住"第三方站点拿用户浏览器当跳板"，私网地址不具备这个威胁面。
CORS_ALLOW_ORIGIN_REGEX = os.getenv(
    "CORS_ALLOW_ORIGIN_REGEX",
    r"^https?://(?:localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(?::\d+)?$",
)

# 日志脱敏：日志与异常堆栈里绝不出现 token / 密钥 / 手机号
LOG_REDACT = os.getenv("LOG_REDACT", "1").lower() not in ("0", "false", "no")
