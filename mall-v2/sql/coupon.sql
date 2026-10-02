-- 阶段8 优惠券模块建表
-- 命名沿用项目风格：前缀-less（coupon / coupon_history），与 orders / product / sku 一致
-- 执行方式：在 MySQL 客户端 source 本文件，或复制下方语句执行

CREATE TABLE `coupon` (
  `id`            bigint       NOT NULL AUTO_INCREMENT,
  `name`          varchar(100) NOT NULL DEFAULT ''            COMMENT '券名称',
  `amount`        decimal(10,2) NOT NULL DEFAULT 0.00        COMMENT '减免金额',
  `min_point`     decimal(10,2) NOT NULL DEFAULT 0.00        COMMENT '使用门槛（满多少可用，0=无门槛）',
  `use_type`      int          NOT NULL DEFAULT 0            COMMENT '0=全场通用 1=指定分类 2=指定商品',
  `category_id`   bigint       DEFAULT NULL                  COMMENT '指定分类ID（use_type=1 时填）',
  `product_id`    bigint       DEFAULT NULL                  COMMENT '指定商品ID（use_type=2 时填）',
  `per_limit`     int          NOT NULL DEFAULT 1            COMMENT '每人限领数',
  `publish_count` int          NOT NULL DEFAULT 0            COMMENT '发放总数',
  `receive_count` int          NOT NULL DEFAULT 0            COMMENT '已领取数',
  `use_count`     int          NOT NULL DEFAULT 0            COMMENT '已使用数',
  `start_time`    datetime     DEFAULT NULL                  COMMENT '生效时间',
  `end_time`      datetime     DEFAULT NULL                  COMMENT '失效时间',
  `note`          varchar(200) DEFAULT NULL                  COMMENT '备注',
  `create_time`   datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（DB 默认，实体/insert 不写）',
  `delete_status` int          NOT NULL DEFAULT 0            COMMENT '逻辑删除 0=未删 1=已删（全局逻辑删）',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='优惠券模板';

CREATE TABLE `coupon_history` (
  `id`         bigint       NOT NULL AUTO_INCREMENT,
  `coupon_id`  bigint       NOT NULL                       COMMENT '关联券ID',
  `member_id`  bigint       NOT NULL                       COMMENT '领取用户ID',
  `coupon_code` varchar(64) DEFAULT NULL                   COMMENT '券码（领取时可生成或留空）',
  `order_id`   bigint       DEFAULT NULL                   COMMENT '核销订单ID',
  `order_sn`   varchar(64)  DEFAULT NULL                   COMMENT '核销订单号',
  `status`     int          NOT NULL DEFAULT 0             COMMENT '0=未使用 1=已使用 2=已过期',
  `create_time` datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '领取时间（DB 默认）',
  `use_time`   datetime     DEFAULT NULL                   COMMENT '使用时间',
  PRIMARY KEY (`id`),
  KEY `idx_coupon_id` (`coupon_id`),
  KEY `idx_member_id` (`member_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户优惠券领取记录';
