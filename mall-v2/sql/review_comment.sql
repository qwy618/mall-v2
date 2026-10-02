-- ============================================================
-- 商品评价系统 DDL（mall_v2）
-- 粒度：按订单项（一个订单项一条评价）
-- 评分：整体单星 1-5 + 文字 + 多图晒单
-- 审核：status 状态机（0待审核 1通过 2驳回），通过后才公开展示
-- 幂等可重复执行
-- ============================================================

-- 1) 评价主表
CREATE TABLE IF NOT EXISTS `comment` (
  `id`              BIGINT(20)   NOT NULL AUTO_INCREMENT,
  `order_item_id`   BIGINT(20)   NOT NULL                COMMENT '关联订单项ID',
  `order_id`        BIGINT(20)   NOT NULL                COMMENT '订单ID',
  `order_sn`        VARCHAR(32)  NOT NULL                COMMENT '订单编号',
  `product_id`      BIGINT(20)   NOT NULL                COMMENT '商品ID',
  `sku_id`          BIGINT(20)   DEFAULT NULL            COMMENT 'SKU ID',
  `product_name`    VARCHAR(255) DEFAULT NULL            COMMENT '商品名称快照',
  `product_pic`     VARCHAR(500) DEFAULT NULL            COMMENT '商品图片快照',
  `member_id`       BIGINT(20)   NOT NULL                COMMENT '评价人会员ID',
  `member_nickname` VARCHAR(64)  DEFAULT NULL            COMMENT '会员昵称（匿名时置空）',
  `member_icon`     VARCHAR(500) DEFAULT NULL            COMMENT '会员头像（匿名时置空）',
  `star`            TINYINT(4)   NOT NULL DEFAULT 5      COMMENT '整体评分 1-5',
  `content`         VARCHAR(1000) DEFAULT NULL           COMMENT '评价内容',
  `pics`            VARCHAR(2000) DEFAULT NULL           COMMENT '晒单图片URL，JSON数组字符串',
  `anonymous`       TINYINT(4)   NOT NULL DEFAULT 0      COMMENT '是否匿名 0否 1是',
  `status`          TINYINT(4)   NOT NULL DEFAULT 0      COMMENT '状态 0待审核 1通过 2驳回',
  `reply_content`   VARCHAR(1000) DEFAULT NULL           COMMENT '后台回复内容',
  `reply_time`      DATETIME     DEFAULT NULL            COMMENT '回复时间',
  `create_time`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '提交时间',
  `update_time`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_order_item` (`order_item_id`)           COMMENT '一个订单项只能评价一次',
  KEY `idx_product` (`product_id`),
  KEY `idx_member` (`member_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品评价表';

-- 2) order_item 增加评价状态标记（便于订单列表直接显示「已评价/未评价」，无需联表）
SET @col_exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = 'mall_v2'
    AND table_name = 'order_item'
    AND column_name = 'comment_status'
);
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `order_item` ADD COLUMN `comment_status` TINYINT(4) NOT NULL DEFAULT 0 COMMENT ''评价状态 0未评价 1已评价'' AFTER `sp_data`',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
