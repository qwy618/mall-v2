-- 013 回填 order_item.product_pic（修复历史订单项图片为空 → 前端显示文字占位）
--
-- 背景：下单落 order_item 时原先只取 sku.pic，而本项目 SKU 多数无独立图（sku.pic 为空串），
--       导致订单项图片存空、订单详情回退成"商品名首字"占位。
--       源头已改为「优先 sku.pic，为空回退 product.pic」；本脚本把历史空图行按同口径补齐。
--
-- 口径与 OrderServiceImpl 下单逻辑、CartServiceImpl.resolvePic 保持一致：
--   product_pic = 有 sku.pic 用 sku.pic，否则用 product.pic；两者都空则保持不动（占位属正常）。
--
-- 可重复执行：只动 product_pic 为 NULL/'' 且能解析出非空图的行。
SET NAMES utf8mb4;

UPDATE order_item oi
JOIN sku s     ON oi.sku_id = s.id
LEFT JOIN product p ON s.product_id = p.id
SET oi.product_pic = CASE
        WHEN s.pic IS NOT NULL AND s.pic <> '' THEN s.pic
        ELSE p.pic
    END
WHERE (oi.product_pic IS NULL OR oi.product_pic = '')
  AND ((s.pic IS NOT NULL AND s.pic <> '')
       OR (p.pic IS NOT NULL AND p.pic <> ''));
