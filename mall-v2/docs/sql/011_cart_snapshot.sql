-- 011 购物车快照列：让 cart_item 落"加入时的商品快照"，
-- 商品/ SKU 下架或删除后，购物车项仍可灰显保留（不再凭空消失）。
-- 可重复执行：用存储过程按 information_schema 存在性守卫逐个 ADD COLUMN。
SET NAMES utf8mb4;

DROP PROCEDURE IF EXISTS mall_v2.add_cart_snapshot_cols;
DELIMITER $$
CREATE PROCEDURE mall_v2.add_cart_snapshot_cols()
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='mall_v2' AND table_name='cart_item' AND column_name='product_id'
  ) THEN
    ALTER TABLE mall_v2.cart_item ADD COLUMN product_id BIGINT NULL COMMENT '商品ID（快照）' AFTER sku_id;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='mall_v2' AND table_name='cart_item' AND column_name='product_name'
  ) THEN
    ALTER TABLE mall_v2.cart_item ADD COLUMN product_name VARCHAR(200) NULL COMMENT '商品名（快照，下架仍可读）' AFTER product_id;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='mall_v2' AND table_name='cart_item' AND column_name='sku_code'
  ) THEN
    ALTER TABLE mall_v2.cart_item ADD COLUMN sku_code VARCHAR(100) NULL COMMENT 'SKU编码（快照）' AFTER product_name;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='mall_v2' AND table_name='cart_item' AND column_name='pic'
  ) THEN
    ALTER TABLE mall_v2.cart_item ADD COLUMN pic VARCHAR(500) NULL COMMENT '商品图（快照）' AFTER sku_code;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='mall_v2' AND table_name='cart_item' AND column_name='sp_data'
  ) THEN
    ALTER TABLE mall_v2.cart_item ADD COLUMN sp_data VARCHAR(500) NULL COMMENT '规格JSON（快照，展示用）' AFTER pic;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='mall_v2' AND table_name='cart_item' AND column_name='price'
  ) THEN
    ALTER TABLE mall_v2.cart_item ADD COLUMN price DECIMAL(10,2) NULL COMMENT '加入时快照单价（下架/缺货时兜底展示）' AFTER sp_data;
  END IF;
END$$
DELIMITER ;
CALL mall_v2.add_cart_snapshot_cols();
DROP PROCEDURE IF EXISTS mall_v2.add_cart_snapshot_cols;
