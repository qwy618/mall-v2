-- 009: 下单幂等 —— orders 增加 submit_token + 唯一键（DB 第二道防线）
-- 配合 Redis 一次性 Token（key = idem:order:{memberId}:{token}，TTL 900s）使用。
-- 正常流量由 Redis Lua 原子认领拦截；本列用于兜底：Redis 被清 / 令牌被复用 / finish 回填丢失时，
-- 靠 uk_submit_token 命中已建订单，返回同一笔单，杜绝重复下单。
-- 唯一键允许 NULL，历史订单（无 token）不受影响。
-- 可重复执行：基于 information_schema 存在性守卫。

SET @c := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orders' AND column_name = 'submit_token'
);

SET @s := IF(@c = 0,
  'ALTER TABLE `orders`
     ADD COLUMN `submit_token` CHAR(36) NULL COMMENT ''下单幂等令牌(一次性)'' AFTER `order_sn`,
     ADD UNIQUE KEY `uk_submit_token` (`submit_token`)',
  'SELECT ''orders.submit_token already exists, skip'' AS msg'
);

PREPARE stmt FROM @s;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
