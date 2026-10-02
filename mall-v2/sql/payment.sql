-- 支付流水表（Mock 工程化闭环 / 后续可平滑扩展真实支付）
-- 用途：支付审计、对账、幂等防重（uk_order_id 一个订单仅一条流水）
-- 说明：支付流水为财务审计数据，物理保留，不逻辑删除（无 delete_status）
-- 执行：MySQL 客户端 source 本文件，或复制下方语句执行

CREATE TABLE `payment` (
  `id`          bigint        NOT NULL AUTO_INCREMENT,
  `order_id`    bigint        NOT NULL                       COMMENT '关联订单ID',
  `order_sn`    varchar(64)   DEFAULT NULL                   COMMENT '订单编号（冗余，便于对账）',
  `member_id`   bigint        NOT NULL                       COMMENT '支付用户ID',
  `amount`      decimal(10,2) NOT NULL DEFAULT 0.00         COMMENT '支付金额（=订单 pay_amount，后端权威）',
  `pay_type`    int           NOT NULL DEFAULT 1             COMMENT '支付方式 1=mock模拟 2=微信 3=支付宝（当前仅 mock）',
  `status`      int           NOT NULL DEFAULT 1             COMMENT '支付状态 0=未支付 1=已支付（mock 即时成功）',
  `pay_time`    datetime      DEFAULT NULL                  COMMENT '支付完成时间',
  `create_time` datetime      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（DB 默认）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_order_id` (`order_id`),
  KEY `idx_member_id` (`member_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支付流水（审计/对账/幂等）';
