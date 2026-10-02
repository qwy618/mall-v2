# 购物车 Redis 缓存（债务17）

## 背景 / 痛点
购物车列表 `CartServiceImpl.list()` 是 C 端**最高频读接口**（进购物车页、进结算页、顶部角标都调）。
改造前每次调用要打 **3 次 DB**：`cart_item` 查行 → `sku` 批量 → `product` 批量（用于在线判定与取实时价）。
大促/秒杀加购风暴会直接打穿 DB。因此把"某会员的购物车原始行"这份读多写少、命中率极高的数据缓存在 Redis。

## 方案（最终落地）
- **缓存结构（Hash）**：
  - 数据 key：`cart:items:{memberId}`，Hash，`field = skuId`，`value = CartItem JSON`（原始行）。
  - 标记 key：`cart:cached:{memberId}`（String），存在即表示"该车已被缓存过（含空车）"。
- **读路径 `loadCartItems(memberId)`**：先查 `cart:cached` 标记 →
  - 命中（含空车）→ 从 `cart:items` Hash 取全部 value 反序列化返回，**全程不查 DB**。
  - 未命中 → 查 DB 行 → `putAll` 进 Hash（`expire`）→ 打 `cart:cached` 标记（即使空车也打，防穿透）→ 返回 DB 行。
- **写后失效 `invalidate(memberId)`**：`add / updateQuantity / delete / check / merge` 落库后调用，
  `cart:items` Hash `clear()` + `cart:cached` 标记 `delete()`，下次读重建。
- **TTL**：`1800s` + 随机 0~300s 抖动（防大量 key 同时过期雪崩）；写后失效为主，TTL 仅兜底。

## 关键决策
1. **只缓存 `cart_item` 原始行，不缓存组装后的 `CartItemVO`**。
   `list()` 里的"在线判定"（商品 `status=1` 才 online 灰显、价格取实时 `sku.price` 而非快照）**仍每次查 `sku/product`**。
   若把 VO（含 online/price/stock）缓存，商品价格改了/下架了缓存感知不到 → 读到陈旧价格/失效状态。
   → 缓存只卸载最重的高频部分（cart_item 行查询），又保住价格/下架实时性。
2. **空车也打标记（防穿透）**：已登录但空车的会员，列表读若每次都查 DB 是浪费；标记存在即返回空，不再打 DB。
3. **复用 Redisson**：portal 已有 `RedissonClient`（订单幂等/优惠券在用），购物车缓存用 `RMap`/`RBucket` + `StringCodec`，不引入新依赖。
4. **序列化**：`ObjectMapper`（Spring 容器，已注册 JavaTimeModule）把 `CartItem` 转 JSON 存 String value。

## 一致性保证
- 写操作严格"先落库、后失效"，绝不会出现"DB 已改但缓存还是旧值"的长期不一致；最多在失效前的极短窗口读到旧值（可被 30min TTL 兜底）。
- 并发写：失效是 clear 整 Hash，不存在部分更新脏数据。

## 验证
- `mvn ... -pl mall-portal -am package` BUILD SUCCESS。
- E2E `scripts/e2e_cart_cache.py`（直连 8081）7/7 绿：
  - 直接改 DB `quantity=999` 且不走接口 → `list` 仍返回 2 ⇒ **读命中缓存**；
  - 调写接口 `check` 触发失效 → `list` 返回 999 ⇒ **写后失效重建**；
  - 重建后再次 `list` 稳定返回 999 ⇒ 命中稳定。

## 边界 / 已知风险
- 未做 Redis 不可用降级（与订单幂等一致，假设 Redis 常驻）；Redis 挂则 `list` 抛错。学习项目可接受。
- 缓存只覆盖"已登录会员"的 DB 购物车；未登录暂存车仍在 `localStorage`（债务16），与缓存解耦。
- 在线判定（sku/product 查询）未缓存——后续可做商品维度缓存进一步卸载，属另一个优化点。
