-- 014 商品域属性表（技术债 1：商品无属性表）
--
-- 背景：规格现在存在 sku.sp_data VARCHAR(500) 里，是一段 JSON 数组文本：
--         [{"key":"颜色","value":"黑色"},{"key":"容量","value":"256G"}]
--       这份数据只够「原样显示」，不够「被查询」和「被规范维护」：
--         ① C 端无「规格参数」区 —— 参数（仅展示、不影响价格库存）无处可放；
--         ② 管理端加 SKU 时「规格」是空白 textarea 手敲 JSON，写错 key 无任何校验；
--         ③ 「按规格筛选」做不到 —— LIKE '%黑色%' 既误命中又用不上索引。
--
-- 设计要点（见 docs/商品域属性表设计.md）：
--   · 规格(SKU 级，影响价格库存) 与 参数(商品级，仅展示) 必须分表 —— 这是参考版
--     product_attribute_value 把两者混在一起的根因。
--   · product_attribute 挂 category_id —— 属性按分类隔离。实测：颜色/容量 属手机数码，
--     尺寸 属服装与电视，系列 属厨卫大电，全局化会让 T 恤编辑页冒出「容量」。
--   · sp_data 仍是**真源**，sku_attribute_value 是它的派生索引（SKU 写入时同步拆解），
--     这样购物车/订单快照/ai-agent/前端等 8+ 处消费方一行都不用改，且随时可回滚。
--
-- ⚠️ 本机 MySQL 是 5.7.36：没有 JSON_TABLE(8.0+)、没有递归 CTE。
--    所以用「UNION ALL 造序号表」展开 JSON 数组，兼容 5.7。
-- ⚠️ 5.7 的 JOIN 顺序坑：派生表**必须出现在引用它的 ON 子句之前**。
--    写成 `FROM sku s JOIN product p ON ... JOIN (派生表) n ON n.i < ...` 会报
--    `Unknown column 'n.i' in 'on clause'` —— 因为解析 `a.name = ... n.i ...` 时
--    n 还没进入作用域。故下面把序号表放在 FROM 首位。
--
-- 可重复执行：建表用 IF NOT EXISTS，回填用 INSERT IGNORE（靠唯一键去重）。
SET NAMES utf8mb4;

-- ============================================================
-- 一、建表
-- ============================================================

-- 属性定义表：某个分类下有哪些属性名
CREATE TABLE IF NOT EXISTS product_attribute (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY               COMMENT '主键ID',
  category_id  BIGINT       NOT NULL                           COMMENT '归属分类，关联category.id（按分类隔离属性，避免全局属性池）',
  name         VARCHAR(64)  NOT NULL                           COMMENT '属性名，如：颜色 / 容量 / 上市年份',
  type         TINYINT      NOT NULL DEFAULT 0                 COMMENT '属性类型：0规格(影响价格库存) 1参数(仅展示)',
  input_type   TINYINT      NOT NULL DEFAULT 1                 COMMENT '录入方式：0手工录入 1从列表选择',
  input_list   VARCHAR(500) DEFAULT NULL                       COMMENT 'type=0时的可选值清单，逗号分隔，如：黑色,蓝色',
  sort         INT          NOT NULL DEFAULT 0                 COMMENT '排序',
  create_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  UNIQUE KEY uk_category_name (category_id, name)              COMMENT '同一分类下属性名唯一：防「颜色」与「颜色 」并存',
  KEY idx_category (category_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT '商品属性定义表';

-- 商品参数值表：只服务 type=1（商品级、仅展示、不影响价格库存）
CREATE TABLE IF NOT EXISTS product_attribute_value (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY              COMMENT '主键ID',
  product_id    BIGINT       NOT NULL                          COMMENT '商品ID，关联product.id',
  attribute_id  BIGINT       NOT NULL                          COMMENT '属性ID，关联product_attribute.id',
  value         VARCHAR(500) NOT NULL                          COMMENT '属性值（单值，如：2023 / 6.1英寸）',
  UNIQUE KEY uk_product_attr (product_id, attribute_id)        COMMENT '一个商品一个属性只有一个值',
  KEY idx_attribute (attribute_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT '商品参数值表(type=1，仅展示)';

-- SKU 规格值表：服务 type=0（SKU 级、影响价格库存）
-- 这张表是参考版缺失的第 3 张表，也是债务 2「按规格筛选」的依赖
CREATE TABLE IF NOT EXISTS sku_attribute_value (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY              COMMENT '主键ID',
  sku_id        BIGINT       NOT NULL                          COMMENT 'SKU ID，关联sku.id',
  attribute_id  BIGINT       NOT NULL                          COMMENT '属性ID，关联product_attribute.id(type=0)',
  value         VARCHAR(255) NOT NULL                          COMMENT '该SKU在这个属性上的取值，如：黑色',
  UNIQUE KEY uk_sku_attr (sku_id, attribute_id)                COMMENT '一个SKU一个规格属性只有一个值',
  KEY idx_attr_value (attribute_id, value)                     COMMENT '按规格筛选走这个索引（债务2）'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT 'SKU规格值表(由sku.sp_data派生)';

-- ============================================================
-- 二、回填①：属性定义（从 sp_data 的 key 反推，按 分类+属性名 去重）
--    实测全库只有 7 种规格名，按分类分散成 16 条定义
-- ============================================================
INSERT IGNORE INTO product_attribute (category_id, name, type, input_type, sort)
SELECT DISTINCT
       p.category_id,
       JSON_UNQUOTE(JSON_EXTRACT(s.sp_data, CONCAT('$[', n.i, '].key'))) AS attr_name,
       0,   -- type=0 规格
       1,   -- input_type=1 从列表选择（规格天然是候选值选一）
       0
FROM (SELECT 0 AS i UNION ALL SELECT 1 UNION ALL SELECT 2
      UNION ALL SELECT 3 UNION ALL SELECT 4) n
JOIN sku s     ON n.i < JSON_LENGTH(s.sp_data)
JOIN product p ON s.product_id = p.id
WHERE s.sp_data IS NOT NULL
  AND s.sp_data NOT IN ('', '[]')
  AND p.category_id IS NOT NULL
  AND COALESCE(JSON_UNQUOTE(JSON_EXTRACT(s.sp_data, CONCAT('$[', n.i, '].key'))), '') <> '';

-- ============================================================
-- 三、回填②：SKU 规格值（每个 SKU 的每个规格键 → 一行）
-- ============================================================
INSERT IGNORE INTO sku_attribute_value (sku_id, attribute_id, value)
SELECT s.id,
       a.id,
       JSON_UNQUOTE(JSON_EXTRACT(s.sp_data, CONCAT('$[', n.i, '].value')))
FROM (SELECT 0 AS i UNION ALL SELECT 1 UNION ALL SELECT 2
      UNION ALL SELECT 3 UNION ALL SELECT 4) n
JOIN sku s     ON n.i < JSON_LENGTH(s.sp_data)
JOIN product p ON s.product_id = p.id
JOIN product_attribute a
  ON a.category_id = p.category_id
 AND a.type = 0
 AND a.name = JSON_UNQUOTE(JSON_EXTRACT(s.sp_data, CONCAT('$[', n.i, '].key')))
WHERE s.sp_data IS NOT NULL
  AND s.sp_data NOT IN ('', '[]')
  AND COALESCE(JSON_UNQUOTE(JSON_EXTRACT(s.sp_data, CONCAT('$[', n.i, '].value'))), '') <> '';

-- ============================================================
-- 四、回填③：把已有取值灌进 input_list
--    目的：管理端的规格下拉一打开就有候选值，运营不必从零输入
--    排序用 LENGTH 优先：字典序会排出「128G,16G,256G,32G」这种别扭顺序
--
-- ⚠️ 再一个 5.7 坑：派生表**不能引用外层列**（没有 LATERAL / 相关派生表）。
--    写成 `SET x = (SELECT ... FROM (SELECT ... WHERE t.aid = a.id) t)` 会报
--    `Unknown column 'a.id' in 'where clause'`。故先聚到临时表，再 JOIN 回写。
-- ============================================================
DROP TEMPORARY TABLE IF EXISTS tmp_attr_input_list;
CREATE TEMPORARY TABLE tmp_attr_input_list (
  attribute_id BIGINT PRIMARY KEY,
  input_list   VARCHAR(500)
);
INSERT INTO tmp_attr_input_list (attribute_id, input_list)
SELECT d.attribute_id,
       GROUP_CONCAT(d.value ORDER BY LENGTH(d.value), d.value SEPARATOR ',')
FROM (SELECT DISTINCT attribute_id, value FROM sku_attribute_value) d
GROUP BY d.attribute_id;

UPDATE product_attribute a
JOIN tmp_attr_input_list t ON t.attribute_id = a.id
SET a.input_list = t.input_list
WHERE a.type = 0;

DROP TEMPORARY TABLE tmp_attr_input_list;

-- ============================================================
-- 五、校验（② 必须等于 ③；④ 的 不一致数 必须为 0）
-- ============================================================
SELECT '① 规格类属性定义数'        AS chk, COUNT(*) AS v FROM product_attribute WHERE type = 0
UNION ALL
SELECT '② sp_data 非空 SKU 数',           COUNT(*)              FROM sku WHERE sp_data IS NOT NULL AND sp_data NOT IN ('', '[]')
UNION ALL
SELECT '③ 已建规格值的 SKU 数(去重)',      COUNT(DISTINCT sku_id) FROM sku_attribute_value
UNION ALL
SELECT '④ 规格值总行数',                  COUNT(*)              FROM sku_attribute_value
UNION ALL
SELECT '⑤ 每SKU规格值数≠JSON长度的SKU数(应为0)',
       (SELECT COUNT(*) FROM (
            SELECT s.id
            FROM sku s
            WHERE s.sp_data IS NOT NULL AND s.sp_data NOT IN ('', '[]')
              AND (SELECT COUNT(*) FROM sku_attribute_value v WHERE v.sku_id = s.id) <> JSON_LENGTH(s.sp_data)
        ) bad);
