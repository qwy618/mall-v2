# mall-v2 · 全栈商城项目

> 基于 **Spring Boot 3 + Vue 3** 从 0 到 1 搭建的一套电商系统，包含 **用户端（C 端）**、**管理端（B 端）**、**后端服务** 与 **AI 智能助手**（Python FastAPI + LangGraph）。
> 领域模型参考开源项目 [macrozheng/mall](https://github.com/macrozheng/mall)，代码与架构为本项目自行实现，用于系统性实战学习。

<p>
  <img alt="Java" src="https://img.shields.io/badge/Java-21-orange">
  <img alt="Spring Boot" src="https://img.shields.io/badge/Spring%20Boot-3.5-6DB33F">
  <img alt="Vue" src="https://img.shields.io/badge/Vue-3.5-42b883">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-5.6-3178c6">
  <img alt="MySQL" src="https://img.shields.io/badge/MySQL-8.0-4479A1">
  <img alt="Redis" src="https://img.shields.io/badge/Redis-7-DC382D">
  <img alt="RabbitMQ" src="https://img.shields.io/badge/RabbitMQ-3-FF6600">
  <img alt="Elasticsearch" src="https://img.shields.io/badge/Elasticsearch-7-005571">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11-3776AB">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-009688">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-ReAct-1C3C3C">
</p>

---

## 目录

- [一、项目简介](#一项目简介)
- [二、功能清单](#二功能清单)
- [三、技术栈](#三技术栈)
- [四、系统架构](#四系统架构)
- [五、仓库结构](#五仓库结构)
- [六、快速开始](#六快速开始)
- [七、配置说明（密钥脱敏）](#七配置说明密钥脱敏)
- [八、核心设计要点](#八核心设计要点)
- [九、设计文档索引](#九设计文档索引)
- [十、已知边界与后续计划](#十已知边界与后续计划)
- [十一、致谢与声明](#十一致谢与声明)

---

## 一、项目简介

本项目**按生产级工程标准落地**，重点放在业务闭环与工程细节上：

- **后端**：Maven 多模块单体（`common / mbg / service / admin / portal`），统一返回体、全局异常、MyBatis-Plus、JWT 鉴权、RBAC 菜单级权限。
- **前端**：两个独立的 Vue 3 + Vite + TS + Element Plus 工程，用户端走暖色生活方式风（自建设计令牌），管理端走经典电商后台风。
- **中间件**：Redis（缓存 / 分布式锁 / 幂等令牌）、RabbitMQ（延迟队列做订单超时取消）、Elasticsearch（商品搜索）、阿里云 OSS（图片对象存储）。
- **智能助手**：独立的 Python 服务（FastAPI + LangGraph ReAct + DeepSeek），**只通过 REST 调用 portal、不直连数据库、不改动 Java 业务代码**，覆盖「导购问答 → 加购 → 订单确认卡片 → 下单」全链路。
- **工程化**：每个复杂特性都配 **设计文档 + 可重复运行的 E2E 脚本 + 实机验证截图**。

---

## 二、功能清单

### 用户端（portal-web）

| 模块 | 能力 |
|---|---|
| 账号 | 手机号注册 / 登录、JWT 鉴权、登录引导弹窗、修改密码、头像上传 |
| 商品 | 首页分类横向导航、商品列表 / 详情（SPU + SKU 规格选择）、全局搜索、ES 关键词搜索 |
| 购物车 | 增删改查、**未登录可用**（localStorage 暂存车）、登录后自动合并、商品快照、Redis 缓存、下架商品灰显不可结算 |
| 订单 | 下单（**一次性 Token 幂等**）、支付（Mock）、取消、超时自动取消、**自动确认收货**、订单详情 / 列表、单号 Redis 按日自增 |
| 营销 | 优惠券领取（**Redis + Lua 防超卖**）、下单抵扣、积分抵扣、会员折扣 |
| 会员 | 等级成长体系（普通 / 银卡 / 金卡 / 钻石）、积分（100 分 = 1 元）、积分流水、成长值自动升级 |
| 售后 | 申请退货 / 我的售后 / 回填物流、退款按订单项实付金额 |
| 其他 | 商品收藏、收货地址管理、评价与晒图 |

### 管理端（mall-admin-v2）

| 模块 | 能力 |
|---|---|
| 认证与权限 | 管理员登录、JWT、**RBAC（角色 → 菜单 → 接口级鉴权）**、动态菜单与路由守卫 |
| 商品 | 商品（SPU）/ SKU 增删改查、品牌管理、分类管理（含逻辑删除） |
| 订单 | 订单列表 / 详情、发货、取消、确认收货、**作废（状态 5 无效订单 + 库存/优惠券/积分/退款全回滚）** |
| 售后 | 退货审核流（同意 / 拒绝 / 收货 / 完成退款并**回冲已赠积分**） |
| 营销 | 优惠券管理 |
| 会员 | 会员 / 等级 / 积分体系 |
| 评价 | 评价审核、回复、删除 |
| 看板 | 仪表盘（ECharts 图表 + 订单实时推送 WebSocket，新单置顶 + 提示音） |

### 智能助手（mall-ai-agent）

| 模块 | 能力 |
|---|---|
| 对话 | C 端悬浮球 + 抽屉，**SSE 流式输出**（打字机效果）、工具调用过程可见 |
| 导购 | 商品搜索 / 详情 / 同款推荐 / 个性化推荐（基于收藏） |
| 交易 | 加购、查看购物车、订单预览、**确认卡片下单**（金额与后端同源试算） |
| 登录态 | 未登录点「加购 / 下单」触发登录引导，登录后无需重开会话 |
| 会话 | 多轮上下文 + **长对话四级降级装配**（工具结果标记化 → 中间轮折叠 → LLM 分段摘要 → 超限裁剪） |

---

## 三、技术栈

| 层次 | 技术 |
|---|---|
| 语言 / 运行时 | Java 21、Node.js 20+、Python 3.11+ |
| 后端框架 | Spring Boot 3.5、Spring Security、MyBatis-Plus 3.5.7、JJWT 0.12、Hutool |
| 数据库 | MySQL 8.0（库名 `mall_v2`） |
| 缓存 / 分布式 | Redis（Redisson：分布式锁、幂等令牌 Lua、缓存） |
| 消息队列 | RabbitMQ（延迟队列：订单超时取消；事件推送） |
| 搜索 | Elasticsearch 7 |
| 对象存储 | 阿里云 OSS |
| 前端 | Vue 3.5、Vite 6、TypeScript 5.6、Element Plus 2.9、Pinia、Vue Router、ECharts、Axios |
| 智能助手 | FastAPI、LangGraph（`create_react_agent`）、DeepSeek（OpenAI 兼容接口）、Redis（会话 / 草稿 / 摘要） |
| 构建 / 部署 | Maven、npm、Nginx |

---

## 四、系统架构

```
                        ┌──────────────────────┐        ┌──────────────────────┐
                        │  portal-web (C 端)    │        │ mall-admin-v2 (B 端) │
                        │  Vue3 + Vite  :3001   │        │ Vue3 + Vite  :5173   │
                        └───┬──────────────┬───┘        └───────────┬──────────┘
                            │ /api         │ /ai                     │ /api + /ws
                            ▼              ▼                         ▼
            ┌───────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
            │ mall-portal :8081 │◄─┤ mall-ai-agent    │  │  mall-admin  :8080   │
            │ 会员端接口 / 下单  │  │ FastAPI     :8090│  │  管理端接口 / 看板    │
            └─────────┬─────────┘  │ LangGraph + LLM  │  └──────────┬───────────┘
                      │            └──────────────────┘             │
                      └────────────────────┬────────────────────────┘
                                           ▼
                     ┌─────────────── Maven 多模块单体 ───────────────┐
                     │  mall-common   统一返回体 / 异常 / 工具         │
                     │  mall-mbg      MyBatis-Plus 实体与 Mapper      │
                     │  mall-service  跨端共享业务（会员等级/积分）     │
                     │  mall-admin    管理端应用                      │
                     │  mall-portal   用户端应用                      │
                     └───────────────────────┬───────────────────────┘
                                             │
        ┌──────────┬──────────┬──────────────┼───────────┬──────────────┐
        ▼          ▼          ▼              ▼           ▼              ▼
     MySQL 8     Redis    RabbitMQ   Elasticsearch   阿里云 OSS      Nginx
    (mall_v2)  (缓存/锁)  (延迟队列/事件)   (商品搜索)     (图片)    (生产反代)
```

> 采用**单体多模块**而非微服务：本项目定位是打牢业务与工程基础，避免过早引入注册中心 / 网关 / RPC 带来的复杂度。
> 智能助手是唯一独立的功能服务，但它**不碰数据库**，只经 REST 复用 portal 的业务能力（含接口级鉴权），因此不破坏上述单体边界。

---

## 五、仓库结构

```
.
├── mall-v2/                  # 后端（Spring Boot 3 多模块）
│   ├── pom.xml               # 父工程：只做依赖版本管理
│   ├── mall-common/          # 公共模块：CommonResult / 异常 / 常量
│   ├── mall-mbg/             # 数据访问模块：实体 + Mapper + XML
│   ├── mall-service/         # 跨端共享业务模块（会员等级 / 积分）
│   ├── mall-admin/           # 管理端应用（端口 8080）
│   ├── mall-portal/          # 用户端应用（端口 8081）
│   ├── sql/                  # 业务增量建表脚本
│   └── docs/                 # 设计文档 + sql/ 增量迁移脚本
│
├── portal-web/               # 用户端前端（Vue3 + Vite，开发端口 3001）
├── mall-admin-v2/            # 管理端前端（Vue3 + Vite，开发端口 5173）
│
└── mall-ai-agent/            # 智能助手服务（Python FastAPI + LangGraph，端口 8090）
    ├── app/                  # 业务码：agent / llm / sessions / store / summarize / tools
    ├── docs/                 # 设计文档（生产化设计 / 状态外置 / 长对话装配）
    ├── scripts/              # 可重复运行的验收脚本（smoke_*）
    └── .env.example          # 配置模板（DEEPSEEK_API_KEY / portal 地址 / Redis）
```

---

## 六、快速开始

### 6.0 环境要求

| 依赖 | 版本 |
|---|---|
| JDK | 21+ |
| Maven | 3.9+ |
| Node.js | 20+ |
| Python | 3.11+（仅智能助手需要） |
| MySQL | 8.0 |
| Docker | 用于中间件（可选，也可本地安装） |

### 6.1 启动中间件（以 Docker 为例）

```bash
# MySQL
docker run -d --name mall-mysql -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=123456 -e MYSQL_DATABASE=mall_v2 mysql:8.0

# Redis
docker run -d --name mall-redis -p 6379:6379 redis:7 --requirepass 123456

# RabbitMQ（带管理台 15672）
docker run -d --name mall-rabbit -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# Elasticsearch
docker run -d --name mall-es -p 9200:9200 \
  -e "discovery.type=single-node" -e "xpack.security.enabled=false" elasticsearch:7.17.0
```

> 中间件不在本机时，改 `application-local.yml` 里的 `host` 即可（见 [七、配置说明](#七配置说明密钥脱敏)）。

### 6.2 初始化数据库

1. 创建数据库：`CREATE DATABASE mall_v2 DEFAULT CHARSET utf8mb4;`
2. 导入**基础表结构**：使用原项目提供的建表脚本
   [`macrozheng/mall` → `document/sql/mall.sql`](https://github.com/macrozheng/mall)。
3. 按顺序导入**本项目的增量脚本**（均为 `CREATE TABLE IF NOT EXISTS`，可重复执行）：

```bash
cd mall-v2
for f in sql/*.sql docs/sql/*.sql; do
  mysql -uroot -p --default-character-set=utf8mb4 mall_v2 < "$f"
done
```

### 6.3 启动后端

```bash
cd mall-v2
# 首次或改动后：打包（-am 必须带，否则会用到陈旧的 mall-mbg）
mvn -o -pl mall-admin -am package -DskipTests
mvn -o -pl mall-portal -am package -DskipTests

# 启动（两个终端）
java -jar mall-admin/target/mall-admin-1.0-SNAPSHOT.jar    # 8080
java -jar mall-portal/target/mall-portal-1.0-SNAPSHOT.jar  # 8081
```

### 6.4 启动前端

```bash
# 用户端
cd portal-web && npm install && npm run dev        # http://localhost:3001

# 管理端
cd mall-admin-v2 && npm install && npm run dev     # http://localhost:5173
```

> 两个前端都已配置 Vite 代理：`/api` → 各自后端（C 端 8081、B 端 8080）；用户端另代理 `/ai` → 智能助手（8090），联调无需额外配置。

### 6.5 启动智能助手（可选）

```bash
cd mall-ai-agent
python -m venv .venv
. .venv/Scripts/activate         # Windows；macOS/Linux 用 source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env             # 填入 DEEPSEEK_API_KEY，按需改 PORTAL_BASE_URL / REDIS_URL
python -m uvicorn app.main:app --port 8090
```

> 助手**不直连数据库**，只经 REST 调用 `mall-portal`（`PORTAL_BASE_URL`，默认 `http://localhost:8081`），所以**必须先启动 portal**。
> 启动后打开用户端，右下角悬浮球即为助手入口；助手自身的 OpenAPI 文档在 http://localhost:8090/docs 。

### 6.6 访问地址与默认账号

| 端 | 地址 | 账号 |
|---|---|---|
| 用户端 | http://localhost:3001 | 手机号自助注册 |
| 管理端 | http://localhost:5173 | `admin` / `macro123`（演示用，生产务必修改） |
| 智能助手 | http://localhost:8090/docs | 复用用户端登录态 |

---

## 七、配置说明（密钥脱敏）

本仓库**不包含任何真实凭据**。所有敏感项在 `application.yml` 中均为占位符：

```yaml
spring:
  datasource:
    password: ${DB_PASSWORD:123456}      # 环境变量 DB_PASSWORD，缺省 123456
oss:
  access-key-id: ${OSS_ACCESS_KEY_ID:}   # 阿里云 AccessKey，缺省为空
  access-key-secret: ${OSS_ACCESS_KEY_SECRET:}
```

真实配置的两种填法（**二选一**）：

1. **环境变量**（推荐用于部署）
   ```bash
   export DB_PASSWORD=your-password
   export OSS_ACCESS_KEY_ID=xxx
   export OSS_ACCESS_KEY_SECRET=yyy
   ```
2. **本地配置文件**（推荐用于开发）
   复制模板并填写：
   ```bash
   cp mall-v2/mall-admin/src/main/resources/application-local.yml.example \
      mall-v2/mall-admin/src/main/resources/application-local.yml
   # portal 同理
   ```
   `application-local.yml` 已在 `.gitignore` 中，**不会被提交**；
   `application.yml` 通过 `spring.profiles.include: local` 自动加载它（文件不存在也能正常启动）。

**智能助手**同样是「只提交模板」：

```bash
cp mall-ai-agent/.env.example mall-ai-agent/.env
```

`.env` 里的 `DEEPSEEK_API_KEY` 需自行填写（**仓库内不含真实 key**），该文件已被 `mall-ai-agent/.gitignore` 排除。

---

## 八、核心设计要点

这些是本项目着力最多、也最能体现工程能力的地方（每项都有设计文档与 E2E 脚本）：

- **下单幂等**：一次性 Token + Redis Lua 原子认领 + `orders.submit_token` 唯一键兜底，解决重复提交。
- **防超卖**：`UPDATE ... WHERE stock >= ?` 原子扣减；优惠券领取用 Redis + Lua 限流。
- **订单超时取消**：RabbitMQ 延迟队列（队列级 TTL）在 30 分钟后自动关单并回滚库存。
- **自动确认收货**：`@Scheduled` 扫描「已发货满 N 天」的订单，复用与手动确认同一套原子流转逻辑，天然幂等。
- **无效订单（状态 5）**：后台作废已付款未发货订单，一次性回滚库存 / 优惠券 / 积分 / 退款，避免资损。
- **会员等级与积分**：成长值自动升级、积分 100 分 = 1 元抵扣、按等级倍率赠送、退货按额度回冲。
- **购物车快照与游客合并**：`cart_item` 落商品快照，未登录用 localStorage 暂存车，登录后合并进会员车。
- **接口级 RBAC**：角色 → 菜单 → 接口映射，拦截器按菜单权限放行。
- **助手金额同源**：确认卡片的应付金额来自 `POST /order/preview`，与真正下单**共用同一套金额计算**，杜绝「展示价 ≠ 结算价」。
- **长对话四级降级装配**：工具结果标记化 → 中间轮折叠 → LLM 分段摘要（以系统消息注入「背景记忆」，**绝不伪装成用户消息**）→ 超限时只裁已被摘要覆盖的最旧轮；**原文只追加不删除，摘要可一键回滚**。

---

## 九、设计文档索引

`mall-v2/docs/` 下为各特性的设计文档（含业务规则、数据模型、并发与幂等、验证方式）：

| 文档 | 主题 |
|---|---|
| [总体架构与部署](mall-v2/docs/总体架构与部署.md) | 模块划分与部署拓扑 |
| [RBAC 后端指南](mall-v2/docs/rbac-backend-guide.md) | 角色菜单权限设计 |
| [接口级鉴权指南](mall-v2/docs/api-level-auth-guide.md) | 菜单 → 接口映射拦截 |
| [下单幂等 Token 设计](mall-v2/docs/下单幂等Token设计.md) | 一次性 Token + Lua |
| [优惠分摊与退款设计](mall-v2/docs/优惠分摊与退款设计.md) | 三类优惠分摊、按实付退款 |
| [购物车快照与合并设计](mall-v2/docs/购物车快照与合并设计.md) | 快照 + 游客合并 |
| [购物车 Redis 缓存设计](mall-v2/docs/购物车Redis缓存设计.md) | 缓存结构与失效策略 |
| [会员等级与积分设计](mall-v2/docs/会员等级与积分设计.md) | 成长值 / 倍率 / 抵扣 |
| [售后退货与订单流水设计](mall-v2/docs/售后退货与订单流水设计.md) | 退货审核流与操作流水 |
| [订单域收尾设计](mall-v2/docs/订单域收尾设计.md) | 自动确认收货 / 无效订单 / 积分回冲 |

`mall-ai-agent/docs/` 下为智能助手的设计文档：

| 文档 | 主题 |
|---|---|
| [智能助手生产化设计](mall-ai-agent/docs/智能助手生产化设计.md) | 工具映射总表、RAG 结构、里程碑 M0→M4 |
| [状态外置与下单一公里设计](mall-ai-agent/docs/M1_状态外置与下单一公里设计.md) | Redis 化会话 / 草稿、下单幂等 |
| [长对话装配设计](mall-ai-agent/docs/M1.5_长对话装配设计.md) | 四级降级、分段摘要、上限裁剪 |

---

## 十、已知边界与后续计划

- **支付为 Mock**：无真实支付通道，仅记录支付 / 退款流水。
- **退款未接入真实渠道**：`payment` 表标记退款状态与金额，不做实际资金划转。
- **成长值不回冲**：退货只回冲积分，成长值（及其触发的等级）不回退。
- **助手 RAG 尚未实现**：当前助手只做**工具调用**（结构化查商品 / 加购 / 下单）；面向口碑、手感、适用场景一类的语义检索（M3）尚未开始。
- **待补**：商品属性表与规格筛选、`min_price` 冗余、商品多图相册、库存锁定与释放、用户名登录。
- **移动端**：uni-app 端尚未开始。

---

## 十一、致谢与声明

- 领域模型与业务灵感来自开源项目 **[macrozheng/mall](https://github.com/macrozheng/mall)**，本项目在其基础上独立设计与实现（代码全部自行编写），用于系统性实战学习。
- 本项目**仅供学习与技术交流**，不用于任何商业用途。
- 仓库中不含任何真实密钥、密码或第三方凭据。
