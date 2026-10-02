-- 012 无效订单（债务8）：payment 增加退款字段，支撑"已付款订单被作废后退款"。
-- 订单状态语义补齐：0待付款 1已付款 2已发货 3已完成 4已关闭（曾有效被取消）5无效订单（被作废）
-- payment.status 语义扩展：0未支付 1已支付 2已退款
-- 可重复执行：用存储过程按 information_schema 存在性守卫逐个 ADD COLUMN。
SET NAMES utf8mb4;

DROP PROCEDURE IF EXISTS mall_v2.add_payment_refund_cols;
DELIMITER $$
CREATE PROCEDURE mall_v2.add_payment_refund_cols()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='mall_v2' AND table_name='payment' AND column_name='refund_amount'
  ) THEN
    ALTER TABLE mall_v2.payment ADD COLUMN refund_amount DECIMAL(10,2) NULL COMMENT '退款金额（订单作废时写入）' AFTER amount;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='mall_v2' AND table_name='payment' AND column_name='refund_time'
  ) THEN
    ALTER TABLE mall_v2.payment ADD COLUMN refund_time DATETIME NULL COMMENT '退款时间' AFTER pay_time;
  END IF;
END$$
DELIMITER ;
CALL mall_v2.add_payment_refund_cols();
DROP PROCEDURE IF EXISTS mall_v2.add_payment_refund_cols;
