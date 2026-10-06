-- 015 商品参数造数（债务 1 的配套数据）
--
-- 为什么需要这个脚本：014 只回填了**规格**（从 sp_data 派生），而**参数**（type=1，
-- 商品级、仅展示）此前全库没有任何数据 —— 屏幕尺寸 / 处理器 / 材质这类信息原先只能
-- 硬塞进 product.sub_title(255)。不造一批数据，C 端「规格参数」区和助手详情问答
-- 做完了也是空的，验收看不出效果。
--
-- 取值口径（尽可能不凭空编造）：
--   ① 优先取商品名/副标题里已经写明的信息，如「天玑8100」「5500mAh」「500GB」
--      「2.8K超清大师屏」「读速高达3500MB/s」；
--   ② 其余按该型号的公开规格填写（本项目是演示库，数据本身为合成数据）。
--
-- 只覆盖有 SKU 的主力商品（用户实际能浏览到的那些）。
-- 可重复执行：属性定义用 INSERT IGNORE（靠 uk_category_name），参数值用 INSERT IGNORE
--            （靠 uk_product_attr）。
SET NAMES utf8mb4;

-- ============================================================
-- 一、参数类属性定义（type=1）
--     sort 从 10 起，让参数排在同分类的规格属性之后
-- ============================================================
INSERT IGNORE INTO product_attribute (category_id, name, type, input_type, sort)
SELECT t.category_id, t.name, 1, 0, t.sort FROM (
  -- 手机通讯
            SELECT 19 AS category_id, '屏幕尺寸' AS name, 10 AS sort
  UNION ALL SELECT 19, '处理器',   11
  UNION ALL SELECT 19, '电池容量', 12
  UNION ALL SELECT 19, '上市年份', 13
  -- T恤
  UNION ALL SELECT 8,  '材质',     10
  UNION ALL SELECT 8,  '版型',     11
  UNION ALL SELECT 8,  '适用季节', 12
  -- 男鞋
  UNION ALL SELECT 29, '鞋面材质', 10
  UNION ALL SELECT 29, '鞋底材质', 11
  -- 电视
  UNION ALL SELECT 35, '屏幕分辨率', 10
  UNION ALL SELECT 35, '刷新率',     11
  UNION ALL SELECT 35, '能效等级',   12
  -- 厨卫大电
  UNION ALL SELECT 39, '能效等级', 10
  UNION ALL SELECT 39, '安装方式', 11
  -- 平板电脑
  UNION ALL SELECT 53, '屏幕尺寸', 10
  UNION ALL SELECT 53, '处理器',   11
  -- 笔记本
  UNION ALL SELECT 54, '屏幕尺寸', 10
  UNION ALL SELECT 54, '处理器',   11
  UNION ALL SELECT 54, '显卡',     12
  -- 硬盘
  UNION ALL SELECT 55, '接口类型', 10
  UNION ALL SELECT 55, '读取速度', 11
) t;

-- ============================================================
-- 二、参数值
--    用 (product_id, 属性名) 定位，再 JOIN 回 product_attribute 拿到 attribute_id
--    —— 这样不必手写 attribute_id，也不会因为 id 变动而插错行
-- ============================================================
INSERT IGNORE INTO product_attribute_value (product_id, attribute_id, value)
SELECT t.pid, a.id, t.val
FROM (
  -- ---------- 手机通讯 ----------
  SELECT 26 AS pid, '屏幕尺寸' AS aname, '5.8英寸'   AS val
  UNION ALL SELECT 26, '处理器',   '麒麟970'
  UNION ALL SELECT 26, '电池容量', '3400mAh'
  UNION ALL SELECT 26, '上市年份', '2018年'

  UNION ALL SELECT 27, '屏幕尺寸', '6.21英寸'
  UNION ALL SELECT 27, '处理器',   '骁龙845'      -- 副标题原文
  UNION ALL SELECT 27, '电池容量', '3400mAh'
  UNION ALL SELECT 27, '上市年份', '2018年'

  UNION ALL SELECT 28, '屏幕尺寸', '5.0英寸'
  UNION ALL SELECT 28, '处理器',   '骁龙425'
  UNION ALL SELECT 28, '电池容量', '3000mAh'
  UNION ALL SELECT 28, '上市年份', '2017年'

  UNION ALL SELECT 29, '屏幕尺寸', '5.5英寸'
  UNION ALL SELECT 29, '处理器',   'A11 仿生'
  UNION ALL SELECT 29, '电池容量', '2675mAh'
  UNION ALL SELECT 29, '上市年份', '2017年'

  UNION ALL SELECT 37, '屏幕尺寸', '6.1英寸'
  UNION ALL SELECT 37, '处理器',   'A15 仿生'
  UNION ALL SELECT 37, '电池容量', '3279mAh'
  UNION ALL SELECT 37, '上市年份', '2022年'

  UNION ALL SELECT 40, '屏幕尺寸', '6.73英寸 2K 超视感屏'   -- 名称原文：2K超视感屏 120Hz高刷
  UNION ALL SELECT 40, '处理器',   '天玑9000+'              -- 名称原文
  UNION ALL SELECT 40, '电池容量', '5160mAh'                -- 副标题原文
  UNION ALL SELECT 40, '上市年份', '2022年'

  UNION ALL SELECT 41, '屏幕尺寸', '6.67英寸 2K 柔性直屏'   -- 名称原文：2K柔性直屏
  UNION ALL SELECT 41, '处理器',   '天玑8100'               -- 名称原文
  UNION ALL SELECT 41, '电池容量', '5500mAh'                -- 名称原文
  UNION ALL SELECT 41, '上市年份', '2022年'

  UNION ALL SELECT 42, '屏幕尺寸', '6.7英寸 直屏'            -- 名称原文：直屏旗舰
  UNION ALL SELECT 42, '处理器',   '骁龙8+'
  UNION ALL SELECT 42, '电池容量', '4460mAh'
  UNION ALL SELECT 42, '上市年份', '2022年'

  UNION ALL SELECT 45, '屏幕尺寸', '6.43英寸'
  UNION ALL SELECT 45, '处理器',   '天玑1300'
  UNION ALL SELECT 45, '电池容量', '4500mAh'                -- 副标题原文：80W超级闪充
  UNION ALL SELECT 45, '上市年份', '2022年'

  -- ---------- T恤 ----------
  UNION ALL SELECT 30, '材质',     '纯棉'                   -- 副标题原文：微弹舒适
  UNION ALL SELECT 30, '版型',     '修身'
  UNION ALL SELECT 30, '适用季节', '夏季'                   -- 副标题原文：2018夏季新品

  UNION ALL SELECT 31, '材质',     '针织棉'                 -- 名称原文：针织布
  UNION ALL SELECT 31, '版型',     '标准'
  UNION ALL SELECT 31, '适用季节', '夏季'

  UNION ALL SELECT 32, '材质',     '纯棉'
  UNION ALL SELECT 32, '版型',     '宽松'
  UNION ALL SELECT 32, '适用季节', '夏季'

  -- ---------- 男鞋 ----------
  UNION ALL SELECT 35, '鞋面材质', '织物'
  UNION ALL SELECT 35, '鞋底材质', '橡胶'
  UNION ALL SELECT 36, '鞋面材质', '皮革拼接织物'
  UNION ALL SELECT 36, '鞋底材质', '橡胶气垫'               -- 名称原文：气垫

  -- ---------- 电视 ----------
  UNION ALL SELECT 33, '屏幕分辨率', '4K 超高清'            -- 副标题原文：4K超高清
  UNION ALL SELECT 33, '刷新率',     '60Hz'
  UNION ALL SELECT 33, '能效等级',   '三级能效'
  UNION ALL SELECT 34, '屏幕分辨率', '4K 超高清'
  UNION ALL SELECT 34, '刷新率',     '60Hz'
  UNION ALL SELECT 34, '能效等级',   '三级能效'

  -- ---------- 厨卫大电 ----------
  UNION ALL SELECT 43, '能效等级', '一级能效'               -- 副标题原文：超一级能效
  UNION ALL SELECT 43, '安装方式', '壁挂式'

  -- ---------- 平板电脑 ----------
  UNION ALL SELECT 38, '屏幕尺寸', '10.9英寸'               -- 名称原文
  UNION ALL SELECT 38, '处理器',   'A14 仿生'

  -- ---------- 笔记本 ----------
  UNION ALL SELECT 39, '屏幕尺寸', '14英寸 2.8K'            -- 名称原文：2.8K超清大师屏
  UNION ALL SELECT 39, '处理器',   'AMD 锐龙'               -- 名称原文：锐龙版
  UNION ALL SELECT 39, '显卡',     '集成显卡'

  -- ---------- 硬盘 ----------
  UNION ALL SELECT 44, '接口类型', 'M.2 接口 (NVMe 协议)'    -- 名称原文
  UNION ALL SELECT 44, '读取速度', '3500MB/s'               -- 副标题原文
) t
JOIN product p           ON p.id = t.pid
JOIN product_attribute a ON a.category_id = p.category_id
                        AND a.name = t.aname
                        AND a.type = 1;

-- ============================================================
-- 三、校验
-- ============================================================
SELECT '① 参数类属性定义数(type=1)' AS chk, COUNT(*) AS v FROM product_attribute WHERE type = 1
UNION ALL
SELECT '② 参数值行数',                COUNT(*)                    FROM product_attribute_value
UNION ALL
SELECT '③ 已有参数的商品数',          COUNT(DISTINCT product_id)  FROM product_attribute_value
UNION ALL
SELECT '④ 参数值挂在规格属性上的行数(应为0)',
       (SELECT COUNT(*) FROM product_attribute_value v JOIN product_attribute a ON a.id = v.attribute_id WHERE a.type <> 1);
