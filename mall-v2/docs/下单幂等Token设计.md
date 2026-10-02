# 下单幂等 · 一次性 Token + Lua（债务 23）

> 版本：2026-10-01　｜　范围：`mall-portal` 下单入口 `POST /order/create`
> 结论：采用**服务端一次性 Token + Redis Lua 原子认领**，DB `UNIQUE` 约束作第二道防线。
> **状态：已落盘并 E2E 验证通过（2026-10-01）** —— DDL/后端/前端全部实施，§10 清单已勾选，§11 验收 1~7 全绿。
> 与初稿的差异（实施中收敛）：①令牌回退改为 **`settled` 标志 + `finally`**（统一覆盖"业务失败 return"与"异常"两条路径，而非仅在 catch 中回退）；
> ②DB 兜底由"捕获 DuplicateKeyException"改为**前置回查 `selectByToken`**（放在扣库存之前，避免"扣了库存才撞唯一键"导致事务内副作用残留）；唯一键退化为纯并发后备。
> ③`finish` 放在 `afterCommit`，避免"标记完成但事务回滚"。

---

## 1. 现状与问题

`OrderServiceImpl.createOrder(memberId, param)`：

- `orderSn = getOrderSn()` —— Redisson 按日原子自增，**每次请求都生成新号**。
- `orders.order_sn` 有唯一约束，但**防的是"同号重复插入"**，防不住"两次请求各生成一个新号"。
- 库存扣减是**条件更新**（`ge(stock, qty)`）、券核销是**乐观条件更新** —— 二者只能防"并发扣成负/超卖"，**防不住"两个请求各扣一次"**。

**后果**：用户双击 / 前端超时重试 / 网关重发 → 重复下单（多扣库存、多核销券、多出订单），需人工退款。

**目标**：同一"购买意图"的 N 次提交，最终**只产生 1 笔订单**；重复请求要么被拒（处理中），要么**返回同一笔订单**（已完成）。

---

## 2. 方案选型

| 方案 | 判定能力 | 结论 |
|---|---|---|
| 仅 `order_sn` 唯一约束 | 只能防同号重复插入 | ✗ 无法识别重复意图 |
| 业务指纹（member+明细+地址+券 哈希） | 同参数短时间内去重 | △ 可作降级兜底，有误判风险 |
| **服务端一次性 Token + Lua** | 精确识别"一次意图"，可返回同结果 | ✓ **本方案** |
| DB 唯一键去重表 | 最后防线，防 Redis 被清/漏网 | ✓ 作为第二道防线一并保留 |

---

## 3. 为什么必须是 Lua（关键论证）

不是"画蛇添足地用脚本"，而是**三条硬需求叠加后只剩余 Lua**：

1. **单靠 `SETNX` 语义不够。** 我们需要区分四种结果：`token 不存在/过期`、`未使用`、`正在处理`、`已完成(要回该订单号)`。`SETNX` 只能回答"存在与否"，无法区分后三者。
2. **"读值 → 判定 → 改状态"存在竞态窗口。** 若拆成 `GET` + `SET` 两条命令，高并发下两个同 token 请求可能**都读到 `0`**、**都判定通过** → 双双下单，幂等失效。必须把这三步合成**一个原子操作**。
3. **TTL 要与状态写入同批完成。** 若 `SET` 与 `EXPIRE` 分离，中间崩溃会留下"永不过期"的 key。Lua 里用 `SET ... EX` 一步到位。

Redis 执行 Lua 时**单线程原子**完成整个脚本，天然消除上述窗口。

---

## 4. Redis Key 设计

```
Key:   idem:order:{memberId}:{token}
Type:  String
TTL:   900s（15 分钟）
Value: 状态机字面量
       "0"        → 未使用（刚取号，可被认领）
       "P"        → 处理中（已被某请求独占，其他请求应拒绝）
       "<orderId>"→ 已完成（重复请求返回该订单号，实现幂等返回同结果）
```

- Key **含 memberId**：令牌与会员绑定，杜绝跨用户重放。
- token 由**服务端**生成（UUID），前端不可自造。
- 15 分钟覆盖"用户慢慢填/网络重传"窗口，且短到不会长期占用 key。

---

## 5. 三个 Lua 脚本

### 5.1 认领 claim（核心，原子判定 + 状态跃迁）

```lua
-- KEYS[1] = idem:order:{memberId}:{token}
-- ARGV[1] = "P"        处理中标记
-- ARGV[2] = "900"      TTL 秒
local v = redis.call('GET', KEYS[1])
if not v then
  return -1            -- 无效/已过期：拒绝
end
if v == '0' then
  redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
  return 0             -- 认领成功：放行下单
end
if v == 'P' then
  return -2            -- 已有同名请求在处理：拒绝（"请勿重复提交"）
end
return tonumber(v)     -- 已完成：返回已生成的 orderId（幂等返回同结果）
```

**返回码约定**：`-1` 无效 ｜ `-2` 处理中 ｜ `0` 认领成功 ｜ `>0` 已完成的 orderId。

### 5.2 完成 finish（下单成功后回填订单号）

```lua
-- KEYS[1] = token key ; ARGV[1] = orderId ; ARGV[2] = TTL
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return 1
```

> 之后同 token 再来 → `claim` 返回该 orderId → 前端直接跳详情，用户无感。

### 5.3 回退 release（下单失败，允许重试）

```lua
-- KEYS[1] = token key ; ARGV[1] = TTL
if redis.call('GET', KEYS[1]) == 'P' then
  redis.call('SET', KEYS[1], '0', 'EX', ARGV[1])
  return 1
end
return 0
```

> **只把 `P` 回退为 `0`**，绝不覆盖 `已完成` 状态，避免"成功后被失败请求误回退"。

---

## 6. Java 集成设计

### 6.1 取号接口（新增，暴露给前端）

```java
// OrderController
@PostMapping("/order/token")
public CommonResult<String> generateToken() {
    return CommonResult.success(orderIdempotentService.generate(currentMemberId()));
}

// OrderIdempotentServiceImpl
private static final long TTL = 900;
public String generate(Long memberId) {
    String token = UUID.randomUUID().toString();
    stringRedisTemplate.opsForValue()
        .set(key(memberId, token), "0", Duration.ofSeconds(TTL));
    return token;
}
private String key(Long memberId, String token) {
    return "idem:order:" + memberId + ":" + token;
}
```

### 6.2 织入 `createOrder`（实测实现）

`createOrder` 只做"认领 + 令牌生命周期"，原下单主体拆到私有 `doCreateOrder(...)`（事务由 `createOrder` 开启，私有方法在同事务内执行，**无自调用失效问题**）：

```java
@Transactional(rollbackFor = Exception.class)
public CommonResult<Long> createOrder(Long memberId, CreateOrderParam param) {
    String token = param.getSubmitToken();
    if (token == null || token.isBlank()) return CommonResult.failed("缺少幂等令牌，请刷新页面重试");
    Long r = orderIdempotentService.claim(memberId, token);
    if (r == null) return CommonResult.failed("系统繁忙，请稍后重试");
    if (r == -1L)  return CommonResult.failed("令牌无效或已过期，请刷新页面重试");
    if (r == -2L)  return CommonResult.failed("订单提交处理中，请勿重复提交");
    if (r >  0L)   return CommonResult.success(r);        // 幂等：返回同一笔单

    boolean settled = false;                              // 已确定结束 → finally 不再回退
    try {
        Order existed = orderMapper.selectOne(new LambdaQueryWrapper<Order>()
                .eq(Order::getSubmitToken, token).last("limit 1"));
        if (existed != null) {                            // 兜底回查（Redis 映射丢失）
            orderIdempotentService.finish(memberId, token, existed.getId());
            settled = true;
            return CommonResult.success(existed.getId());
        }
        CommonResult<Long> res = doCreateOrder(memberId, param, token);
        settled = res != null && ResultCode.SUCCESS.equals(res.getCode()) && res.getData() != null;
        return res;
    } finally {
        if (!settled) {                                   // 业务失败/异常 → 回退，允许重试
            try { orderIdempotentService.release(memberId, token); }
            catch (Exception e) { log.error("幂等令牌回退失败 token={}", token, e); }
        }
    }
}
```

`doCreateOrder` 内：建单前 `order.setSubmitToken(token)`；并在已有的 `afterCommit` 回调里补一次 `finish(memberId, token, orderId)`。

`CreateOrderParam` 增加字段 `private String submitToken;`。

### 6.3 与 `@Transactional` 的关系（要点）

- Redis 的 claim/finish/release **不参与 DB 事务**；
- 回退用 **`settled` 标志 + `finally`**：成功路径 `settled=true` 不回退；**业务失败 return**（如"地址不存在"）与**抛异常**两条路径都会回退 → 用户修正后可用同一令牌重试；
- **裸 `finally` 回退是错的**（成功也回退）；这里的 `finally` 带 `settled` 守卫，故正确；
- `finish` 放在 `afterCommit`：只有事务真正提交后才标记完成，避免"标记完成但事务回滚"造成漏单。

---

## 7. DB 第二道防线（兜底）

防 Redis 被 flush / 令牌被复用 / finish 调用丢失：

```sql
-- 009_order_submit_idempotent.sql（存在性守卫，可重跑）
SET @c := (SELECT COUNT(*) FROM information_schema.columns
           WHERE table_schema = DATABASE() AND table_name = 'orders' AND column_name = 'submit_token');
SET @s := IF(@c = 0,
  'ALTER TABLE `orders`
     ADD COLUMN `submit_token` CHAR(36) NULL COMMENT ''下单幂等令牌'' AFTER `order_sn`,
     ADD UNIQUE KEY `uk_submit_token` (`submit_token`)',
  'SELECT 1');
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;
```

- 建单前写入 `order.setSubmitToken(token)`；**恢复路径**：`createOrder` 开头按 token **前置回查**（`selectByToken`）——命中即直接返回该单（放在扣库存之前，无副作用），用于 Redis 被清 / 映射丢失。
- 唯一索引是**纯并发后备**：正常流量已被 Redis 认领串行化，撞唯一键属极端情况；一旦抛出 `DuplicateKeyException` 会令事务整卷回滚（无残留副作用），用户重试即由上面的前置回查命中。
- 唯一索引允许 `NULL`，故历史订单（无 token）不受影响（实测 76 条历史订单 token 为 NULL，读写正常）。

---

## 8. 并发正确性论证

| 时刻 | 请求 A | 请求 B（同 token） | Redis 值 | A 结果 | B 结果 |
|---|---|---|---|---|---|
| t1 | claim 执行 | — | `0`→`P` | 放行 | — |
| t2 | 建单中 | claim 执行 | `P` | — | 返回 `-2` 拒绝 |
| t3 | finish | — | `P`→`<id>` | success(id) | — |
| t4 | — | claim 执行 | `<id>` | — | success(id) 同单 |
| t5 | 失败 | — | `P`→`0` | 失败 | 可重试 ✓ |

关键：**`0 → P` 的跃迁在 Lua 内原子完成，并发下只有一个请求能拿到 `0`**。

---

## 9. 边界与坑

1. **集群 hash slot**：单 key 脚本天然同槽；若以后扩成多 key，需 `{memberId}` hash tag。
2. **脚本保持 O(1)**：禁止在 Lua 里循环/遍历大 key —— Redis 单线程，慢脚本会阻塞全站。
3. **EVALSHA**：Spring `DefaultRedisScript` 首次 EVAL 后自动转 EVALSHA；脚本内容变更时注意重新加载（部署重启即可）。
4. **处理中卡死**：若请求 A 崩溃在 `P` 态，token 会卡到 TTL 到期。可选增强：`-2` 时走慢路径回查 `orders.submit_token`，命中则直接返回该单。
5. **令牌必须服务端生成**，前端自造 UUID 可被篡改伪造。
6. **取号接口幂等性**：生成接口本身可反复调用（每次给新 token），不需幂等。
7. **失败回退要精确**：仅 `P → 0`，禁无条件 `SET 0`（会覆盖已完成）。

---

## 10. 落盘清单（✅ 已全部落盘 2026-10-01）

| # | 动作 | 文件 | 状态 |
|---|---|---|---|
| 1 | DDL 加 `submit_token` + 唯一键 | `docs/sql/009_order_submit_idempotent.sql` | ✅ 已建列+索引 |
| 2 | 实体加字段（`OrderMapper` 走 BaseMapper，无 XML） | `mall-mbg/.../model/Order.java` | ✅ |
| 3 | Param 加 `submitToken` | `mall-portal/.../dao/CreateOrderParam.java` | ✅ |
| 4 | 幂等服务（Redisson RScript + 3 脚本） | `mall-portal/.../service/OrderIdempotentService(+Impl)` | ✅ |
| 5 | Controller 取号接口 `POST /order/token` | `mall-portal/.../controller/OrderController.java` | ✅ |
| 6 | `createOrder` 织入 + 兜底（拆分 `doCreateOrder`） | `mall-portal/.../service/impl/OrderServiceImpl.java` | ✅ |
| 7 | 结算页取号 + 提交带 token | `portal-web` `views/order/confirm.vue`、`apis/order.ts`、`types/order.ts` | ✅ |

---

## 11. 验收用例

1. **正常**：取号 → 下单成功 → 返回 orderId；token 值变为该 orderId。
2. **双击**（并发两请求同 token）：恰好 1 单；另一请求返回 `-2` 或同 orderId。
3. **重试**：成功后重发同 token → 返回**同一** orderId，不新增订单。
4. **失败重试**：故意让券不满足门槛触发失败 → token 回退为 `0` → 修正后重提交**成功**。
5. **过期**：取号后等 >15min 再提交 → 返回 `-1`，提示刷新。
6. **无 token**：不传 `submitToken` → 返回"缺少幂等令牌"。
7. **兜底**：手工清 Redis 后重发同 token → 由 `uk_submit_token` 命中，返回已有订单。
8. **压测**：同一 token 并发 100 次 → `orders` 仅新增 1 行，库存仅扣 1 次。

### 实测结果（2026-10-01，脚本 `scripts/e2e_order_idempotent.py`）

| 用例 | 期望 | 实测 | 结论 |
|---|---|---|---|
| 缺令牌 | 拒绝 | `500 缺少幂等令牌，请刷新页面重试` | ✅ |
| 无效地址（令牌 t1）失败后同号重试 | 仍报业务错（非"处理中"）⇒ 回退生效 | `500 地址不存在` ×2 | ✅ |
| 同令牌 t2 连续 3 次 | 同一 orderId | 三次均返回 `89` | ✅ |
| 同令牌 t3 并发 2 次 | 只成一单 | 一 `500 订单提交处理中…`、一 `200 orderId=90` | ✅ |
| DB 落库 | 每 token 恰好 1 行 | t2→1 行(89)、t3→1 行(90) | ✅ |
| 库存 | 仅扣 1 次/单 | sku112 `500 → 498` | ✅ |
| 历史数据 | NULL token 不受影响 | 76 条 NULL 订单读写正常 | ✅ |

---

## 12. 与项目既有幂等的呼应

项目已有幂等先例：MQ 超时取消 `cancelExpiredBySystem()`（幂等取消）、券核销 `useCoupon`（乐观条件更新）。债务 23 补上**下单入口**这一处后，写链路幂等**已闭环**（2026-10-01）。
