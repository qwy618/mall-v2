-- ============================================================================
-- 016 库存锁定释放（债务 5）：sku.lock_stock 数据修复 + 不变量约定
-- ============================================================================
-- 本次是**代码改造为主**（见 SkuStockService），本文件只做两件事：
--   1. 修复 lock_stock 的历史脏数据
--   2. 把「两个计数器」的口径与不变量写成可执行的巡检语句，便于以后回归
--
-- 【列本身】sku.lock_stock 早已存在（默认 0），此前无任何代码读写，
--   字段注释即设计意图：「锁定库存：下单未付款时预占，防止超卖」。
--
-- 【语义】
--   stock       实物库存（真正在库里的数量）
--   lock_stock  锁定库存（已被「待支付订单」预占的数量）
--   可售库存 = stock - lock_stock   ← 一切「还有没有货」的判断都必须用这个
--
-- 【状态流转 ↔ 库存动作】
--   下单(新建 status=0)     lock()      lock_stock += n   （条件 stock - lock_stock >= n）
--   支付(0 → 1)            consume()   stock -= n, lock_stock -= n  （条件 lock_stock >= n）
--   取消/超时(0 → 4)        release()   lock_stock -= n   （条件 lock_stock >= n，天然幂等）
--   作废(1 → 5)            restore()   stock += n
--   发货/完成/收货         不动作
--
-- 【不变量】恒成立，任何时刻都该满足：
--   lock_stock >= 0  AND  lock_stock <= stock
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. 历史脏数据修复（2026-10-07 执行时实测 4 行）
--    成因：DB 直连导入的种子数据，非本仓库代码所为（git 全历史搜不到 lock_stock 写入）。
--    依据：执行时全库「待支付订单 = 0 笔」→ 不存在任何未释放的预占 →
--          所有 SKU 的 lock_stock 正确值都应当是 0。
--    ⚠️ 若将来在「存在待支付订单」的库上重跑，不能直接照抄这句 —— 那会把真实预占抹掉。
-- ---------------------------------------------------------------------------
SELECT id, product_id, stock, lock_stock FROM sku WHERE lock_stock <> 0 ORDER BY id;  -- 修复前快照

UPDATE sku SET lock_stock = 0 WHERE lock_stock <> 0;

-- ---------------------------------------------------------------------------
-- 2. 修复后校验 / 日常巡检（两个查询都该返回 0）
-- ---------------------------------------------------------------------------
-- 2.1 不变量巡检：两个计数都应为 0
SELECT SUM(lock_stock < 0)     AS lock负数行数,
       SUM(lock_stock > stock) AS lock超实物库存行数
FROM sku;

-- 2.2 对账巡检：lock_stock 应恰好等于「该 SKU 在待支付订单里的数量之和」
--     （两边不一致说明有锁定泄漏或重复释放）
SELECT s.id AS sku_id,
       s.stock,
       s.lock_stock                                        AS 实际锁定,
       IFNULL(o.待支付数量, 0)                              AS 应有锁定,
       (s.lock_stock - IFNULL(o.待支付数量, 0))              AS 差额
FROM sku s
LEFT JOIN (
    SELECT oi.sku_id, SUM(oi.quantity) AS 待支付数量
    FROM order_item oi
    JOIN orders o ON o.id = oi.order_id
    WHERE o.status = 0 AND o.delete_status = 0
    GROUP BY oi.sku_id
) o ON o.sku_id = s.id
HAVING 差额 <> 0;
