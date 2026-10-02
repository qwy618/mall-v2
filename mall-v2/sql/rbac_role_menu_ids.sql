-- RBAC 阶段（P0）：给角色表增加「可见菜单」字段
-- 作用：存储该角色可访问的前端路由 name（如 Dashboard,Brand），逗号分隔。
--       超级管理员(admin) 留空 = 全部可见（前端 canAccess 短路）。
-- 在 mall_v2 库执行（MySQL 8.x）。幂等：列已存在则跳过。

SET @dbname = DATABASE();
SET @tbname = 'ums_role';
SET @colname = 'menu_ids';
SET @exists = (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = @dbname AND table_name = @tbname AND column_name = @colname
);
SET @sql = IF(
  @exists = 0,
  'ALTER TABLE ums_role ADD COLUMN menu_ids VARCHAR(500) NULL DEFAULT NULL COMMENT ''角色可见菜单：前端路由name逗号分隔；超级管理员留空=全部可见''',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 给「商品管理员(product)」预置可见菜单（不含 System 系统管理，体现角色差异）
UPDATE ums_role
SET menu_ids = 'Dashboard,Brand,Category,Product,Order,Coupon'
WHERE code = 'product';

-- 说明：admin 角色 menu_ids 保持为空（前端 admin 短路全可见），无需在此设置。
