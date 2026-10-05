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
