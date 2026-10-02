-- ============================================================
-- 优惠券测试数据（覆盖 use_type 0/1/2 三种类型）
-- 用法：在 MySQL 客户端执行本文件（mysql -u<user> -p <db> < coupon_test_data.sql
--       或 Navicat 直接打开运行）。
-- 执行前：把下方 @member_phone 改成【你登录用的手机号】。
-- 执行后：用 SELECT 输出的 test_sku_id 去"立即购买"，三张券都能在确认订单页看到。
-- ============================================================

-- 1) 定位你的登录会员（券必须发给实际登录的那个会员才看得到）
SET @member_phone = '13800000000';                 -- ← 改成你自己的手机号
SET @member_id = (SELECT id FROM member WHERE phone = @member_phone);
SELECT @member_id AS member_id;                     -- 若返回 NULL，说明手机号不对（该会员不存在），请先注册/登录

-- 2) 探测一个真实商品及其分类（让指定分类/指定商品券能命中）
SET @product_id  = (SELECT id FROM product LIMIT 1);
SET @category_id = (SELECT category_id FROM product WHERE id = @product_id);

-- 3) 插入三张测试券：全场 / 指定分类 / 指定商品（门槛都设为 1 元，任意订单都能达门槛）
INSERT INTO coupon (name, amount, min_point, use_type, category_id, product_id, per_limit, publish_count, receive_count, use_count, start_time, end_time, note)
VALUES ('测试-全场满1减5',     5.00, 1.00, 0, NULL,          NULL,         1, 100, 0, 0, NOW(), DATE_ADD(NOW(), INTERVAL 7 DAY), 'coupon-test');
SET @c1 = LAST_INSERT_ID();

INSERT INTO coupon (name, amount, min_point, use_type, category_id, product_id, per_limit, publish_count, receive_count, use_count, start_time, end_time, note)
VALUES ('测试-指定分类满1减8', 8.00, 1.00, 1, @category_id,  NULL,         1, 100, 0, 0, NOW(), DATE_ADD(NOW(), INTERVAL 7 DAY), 'coupon-test');
SET @c2 = LAST_INSERT_ID();

INSERT INTO coupon (name, amount, min_point, use_type, category_id, product_id, per_limit, publish_count, receive_count, use_count, start_time, end_time, note)
VALUES ('测试-指定商品满1减6', 6.00, 1.00, 2, NULL,          @product_id, 1, 100, 0, 0, NOW(), DATE_ADD(NOW(), INTERVAL 7 DAY), 'coupon-test');
SET @c3 = LAST_INSERT_ID();

-- 4) 给该会员发放这三张券（coupon_history.status=0 未使用）
INSERT INTO coupon_history (coupon_id, member_id, coupon_code, order_id, order_sn, status, use_time)
VALUES
  (@c1, @member_id, CONCAT('TEST', @c1), NULL, NULL, 0, NULL),
  (@c2, @member_id, CONCAT('TEST', @c2), NULL, NULL, 0, NULL),
  (@c3, @member_id, CONCAT('TEST', @c3), NULL, NULL, 0, NULL);

-- 5) 输出用于测试的 sku：用这个 sku 立即购买，指定分类券/指定商品券都能命中
SELECT s.id AS test_sku_id, s.product_id, p.category_id
FROM sku s
JOIN product p ON s.product_id = p.id
WHERE p.id = @product_id
LIMIT 1;

SELECT '测试券已发放完成，请登录该手机号，在确认订单页查看三张券' AS tips;
