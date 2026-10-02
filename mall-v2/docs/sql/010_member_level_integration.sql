-- 010: 会员等级 + 积分体系（债务 18/19）
-- 1) member 增加 level_id / integration / growth / history_integration
-- 2) 新表 member_level：等级配置（升级门槛成长值 + 积分倍率 + 会员折扣）
-- 3) 新表 member_integration_history：积分变动流水（对账 + 明细页）
-- 4) orders 增加 promotion_amount（会员折扣）/ use_integration / integration_amount（积分抵扣）
--    顺带补上债务 6 里 orders 缺失的 promotion_amount、integration_amount 两列。
--
-- 业务规则（与后端 IntegrationService / MemberLevelService 一致）：
--   * 赠送积分 = floor(实付金额 × 等级积分倍率%)，成长值 = 实付金额（1 元 = 1 成长值）
--   * 等级由成长值决定，取 growth_point <= 成长值 的最高档
--   * 积分抵扣：100 积分 = 1 元，抵扣上限 = 商品总额 − 会员折扣 − 优惠券
--
-- 可重复执行：表用 CREATE TABLE IF NOT EXISTS，加列用 information_schema 存在性守卫，
-- 等级数据用 INSERT ... ON DUPLICATE KEY UPDATE 幂等 upsert。
--
-- 注意：本脚本含中文字面量（等级名/备注），必须显式声明 utf8mb4，
--       否则 Windows 下 mysql.exe 默认连接字符集会报 1366 Incorrect string value。

SET NAMES utf8mb4;

-- ============ 1. member 增加等级/积分/成长值 ============
SET @c := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'member' AND column_name = 'level_id'
);
SET @s := IF(@c = 0,
  'ALTER TABLE `member`
     ADD COLUMN `level_id` BIGINT NOT NULL DEFAULT 1 COMMENT ''会员等级id(member_level.id)'',
     ADD COLUMN `integration` INT NOT NULL DEFAULT 0 COMMENT ''当前可用积分'',
     ADD COLUMN `growth` INT NOT NULL DEFAULT 0 COMMENT ''成长值(决定会员等级)'',
     ADD COLUMN `history_integration` INT NOT NULL DEFAULT 0 COMMENT ''累计获得积分(只增不减)'' ',
  'SELECT ''member level/integration columns already exist, skip'' AS msg'
);
PREPARE stmt FROM @s;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ============ 2. member_level 等级配置表 ============
CREATE TABLE IF NOT EXISTS `member_level` (
  `id`               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '等级id',
  `name`             VARCHAR(32)  NOT NULL                COMMENT '等级名称',
  `growth_point`     INT          NOT NULL DEFAULT 0      COMMENT '达到该成长值即此等级(含)',
  `integration_rate` INT          NOT NULL DEFAULT 100    COMMENT '下单赠送积分倍率(%)：100=1倍 150=1.5倍',
  `discount_rate`    INT          NOT NULL DEFAULT 100    COMMENT '会员折扣(%):100=原价 98=98折',
  `note`             VARCHAR(200)          DEFAULT NULL   COMMENT '等级权益说明',
  `create_time`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_growth_point` (`growth_point`),
  CONSTRAINT `ck_level_rate` CHECK (`integration_rate` > 0 AND `discount_rate` > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会员等级配置';

-- 四档等级（幂等 upsert，重复执行只更新不新增）
INSERT INTO `member_level`
  (`id`, `name`, `growth_point`, `integration_rate`, `discount_rate`, `note`)
VALUES
  (1, '普通会员', 0,     100, 100, '基础等级，下单 1 倍积分'),
  (2, '银卡会员', 1000,  120, 99,  '成长值满 1000：1.2 倍积分，99 折'),
  (3, '金卡会员', 5000,  150, 98,  '成长值满 5000：1.5 倍积分，98 折'),
  (4, '钻石会员', 20000, 200, 95,  '成长值满 20000：2 倍积分，95 折')
ON DUPLICATE KEY UPDATE
  `name`             = VALUES(`name`),
  `integration_rate` = VALUES(`integration_rate`),
  `discount_rate`    = VALUES(`discount_rate`),
  `note`             = VALUES(`note`);

-- ============ 3. member_integration_history 积分流水 ============
CREATE TABLE IF NOT EXISTS `member_integration_history` (
  `id`                BIGINT       NOT NULL AUTO_INCREMENT,
  `member_id`         BIGINT       NOT NULL                COMMENT '会员id',
  `order_id`          BIGINT                DEFAULT NULL   COMMENT '关联订单id(下单抵扣/订单赠送/退货扣回)',
  `order_sn`          VARCHAR(32)           DEFAULT NULL   COMMENT '关联订单号(冗余，避免联表)',
  `change_type`       TINYINT      NOT NULL                COMMENT '1下单赠送 2下单抵扣 3退货扣回 4管理员调整',
  `change_count`      INT          NOT NULL                COMMENT '变动值：正=获得 负=消耗',
  `integration_after` INT          NOT NULL DEFAULT 0      COMMENT '变动后可用积分余额(对账用)',
  `operate_man`       VARCHAR(64)           DEFAULT NULL   COMMENT '操作人(会员{id}/system/管理员名)',
  `operate_note`      VARCHAR(200)          DEFAULT NULL   COMMENT '备注',
  `create_time`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_member_time` (`member_id`, `create_time`),
  KEY `idx_order` (`order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会员积分流水';

-- ============ 4. orders 增加会员折扣 / 积分抵扣列 ============
SET @c := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orders' AND column_name = 'integration_amount'
);
SET @s := IF(@c = 0,
  'ALTER TABLE `orders`
     ADD COLUMN `promotion_amount`   DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT ''会员折扣金额'' AFTER `coupon_amount`,
     ADD COLUMN `use_integration`    INT           NOT NULL DEFAULT 0    COMMENT ''使用的积分数''   AFTER `promotion_amount`,
     ADD COLUMN `integration_amount` DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT ''积分抵扣金额''   AFTER `use_integration` ',
  'SELECT ''orders promotion/integration columns already exist, skip'' AS msg'
);
PREPARE stmt FROM @s;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
