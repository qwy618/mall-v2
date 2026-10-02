-- 债务7：order_item 优惠分摊字段
-- 下单时把整单优惠按"本行原价小计"比例摊到每行，并持久化 real_amount（实际实付）。
-- 退款（债务14）一律按 real_amount 退，杜绝薅羊毛。
-- 对应改动：OrderItem 实体、OrderItemMapper.xml、OrderServiceImpl.allocateDiscount()

ALTER TABLE order_item
  ADD COLUMN coupon_amount       DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '本行分摊的优惠券金额',
  ADD COLUMN promotion_amount    DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '本行分摊的促销/满减金额',
  ADD COLUMN integration_amount  DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '本行分摊的积分抵扣金额',
  ADD COLUMN real_amount         DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '本行实际实付 = price*qty - 各项分摊';
