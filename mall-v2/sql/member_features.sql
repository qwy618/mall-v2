-- 会员收藏表（我的收藏）
-- 收藏粒度：会员 + 商品（同一商品只收藏一次，靠唯一索引保证）
-- product_name / product_pic / product_price 在收藏时快照，避免商品价格变动后收藏列表显示异常
CREATE TABLE IF NOT EXISTS member_product_collection (
  id           BIGINT       NOT NULL AUTO_INCREMENT,
  member_id    BIGINT       NOT NULL,
  product_id   BIGINT       NOT NULL,
  product_name VARCHAR(255) DEFAULT NULL,
  product_pic  VARCHAR(500) DEFAULT NULL,
  product_price DECIMAL(10,2) DEFAULT 0,
  create_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_member_product (member_id, product_id),
  KEY idx_member_ctime (member_id, create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会员商品收藏';
