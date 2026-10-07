package com.macro.mall.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.macro.mall.mbg.dto.SpecFacetCount;
import com.macro.mall.mbg.dto.SpecQueryGroup;
import com.macro.mall.mbg.mapper.ProductAttributeMapper;
import com.macro.mall.mbg.mapper.ProductAttributeValueMapper;
import com.macro.mall.mbg.mapper.ProductMapper;
import com.macro.mall.mbg.mapper.SkuAttributeValueMapper;
import com.macro.mall.mbg.mapper.SkuMapper;
import com.macro.mall.mbg.model.Product;
import com.macro.mall.mbg.model.ProductAttribute;
import com.macro.mall.mbg.model.ProductAttributeValue;
import com.macro.mall.mbg.model.Sku;
import com.macro.mall.mbg.model.SkuAttributeValue;
import com.macro.mall.service.ProductAttributeService;
import com.macro.mall.service.vo.AttributeItemVO;
import com.macro.mall.service.vo.SpecFacetVO;
import com.macro.mall.service.vo.SpecFacetValueVO;
import com.macro.mall.service.vo.SpecMatchVO;
import com.macro.mall.service.vo.SpecOptionVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 商品属性服务实现（见 ProductAttributeService 的说明）。
 *
 * 核心约定：**sku.sp_data 是真源，sku_attribute_value 是派生索引**。
 * 所以这里的同步只做「按 sp_data 重建索引」，绝不反向回写 sp_data，
 * 这样购物车快照 / 订单快照 / ai-agent / 前端渲染等 8+ 处消费方一行都不用改。
 */
@Service
@Slf4j
public class ProductAttributeServiceImpl implements ProductAttributeService {

    /** 对齐 product_attribute.input_list 的列宽 */
    private static final int MAX_INPUT_LIST_LEN = 500;

    @Autowired
    private ProductAttributeMapper productAttributeMapper;
    @Autowired
    private ProductAttributeValueMapper productAttributeValueMapper;
    @Autowired
    private SkuAttributeValueMapper skuAttributeValueMapper;
    @Autowired
    private ProductMapper productMapper;
    @Autowired
    private SkuMapper skuMapper;
    @Autowired
    private ObjectMapper objectMapper;

    // ==================== 写：SKU 规格同步 ====================

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void syncSkuSpecs(Long skuId, String spData) {
        if (skuId == null) {
            return;
        }
        // 幂等：先清空该 SKU 的旧规格值，再按 sp_data 重建。
        // 用「先删后插」而不是 diff，是因为还要天然处理「规格值被改掉」的情况。
        skuAttributeValueMapper.delete(
                new LambdaQueryWrapper<SkuAttributeValue>().eq(SkuAttributeValue::getSkuId, skuId));

        List<SpecPair> pairs = parseSpecs(spData);
        if (pairs.isEmpty()) {
            return;
        }
        Sku sku = skuMapper.selectById(skuId);
        if (sku == null) {
            log.warn("同步规格跳过：SKU {} 不存在", skuId);
            return;
        }
        Long categoryId = categoryIdOfProduct(sku.getProductId());
        if (categoryId == null) {
            // 商品没有分类 → 属性无处归属。宁可不同步，也不能把属性塞进「全局池」，
            // 那正是参考版 product_attribute 缺 category_id 的缺陷。
            log.warn("同步规格跳过：SKU {} 所属商品 {} 没有 category_id", skuId, sku.getProductId());
            return;
        }

        for (SpecPair pair : pairs) {
            Long attrId = resolveSpecAttributeId(categoryId, pair.key());
            if (attrId == null) {
                continue;
            }
            SkuAttributeValue row = new SkuAttributeValue();
            row.setSkuId(skuId);
            row.setAttributeId(attrId);
            row.setValue(pair.value());
            try {
                skuAttributeValueMapper.insert(row);
            } catch (DuplicateKeyException e) {
                // sp_data 里同一个 key 出现两次（脏数据）→ 让唯一键挡住，不中断整次保存
                log.warn("SKU {} 的规格属性「{}」重复，已忽略后一个值 {}", skuId, pair.key(), pair.value());
                continue;
            }
            appendInputList(attrId, pair.value());
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void removeSkuSpecs(Long skuId) {
        if (skuId == null) {
            return;
        }
        // sku 是物理删除，派生索引必须手动清，否则留孤儿行（按规格筛选时会查出已删 SKU）
        skuAttributeValueMapper.delete(
                new LambdaQueryWrapper<SkuAttributeValue>().eq(SkuAttributeValue::getSkuId, skuId));
    }

    // ==================== 写：商品参数 ====================

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void saveProductParams(Long productId, List<AttributeItemVO> items) {
        if (productId == null) {
            return;
        }
        productAttributeValueMapper.delete(
                new LambdaQueryWrapper<ProductAttributeValue>()
                        .eq(ProductAttributeValue::getProductId, productId));
        if (items == null || items.isEmpty()) {
            return;
        }
        // 只允许写 type=1 的参数：前端可能把规格属性的 id 也传上来，别混进参数表
        Set<Long> paramAttrIds = productAttributeMapper.selectList(
                        new LambdaQueryWrapper<ProductAttribute>()
                                .eq(ProductAttribute::getType, ProductAttribute.TYPE_PARAM))
                .stream().map(ProductAttribute::getId).collect(Collectors.toSet());

        for (AttributeItemVO item : items) {
            if (item == null || item.getAttributeId() == null) {
                continue;
            }
            String value = item.getValue() == null ? "" : item.getValue().trim();
            if (value.isEmpty()) {
                continue;   // 表单留空 = 不填这个参数
            }
            if (!paramAttrIds.contains(item.getAttributeId())) {
                log.warn("保存参数跳过：属性 {} 不存在或不是参数(type=1)", item.getAttributeId());
                continue;
            }
            ProductAttributeValue row = new ProductAttributeValue();
            row.setProductId(productId);
            row.setAttributeId(item.getAttributeId());
            row.setValue(value);
            try {
                productAttributeValueMapper.insert(row);
            } catch (DuplicateKeyException e) {
                log.warn("商品 {} 的参数属性 {} 重复，已忽略", productId, item.getAttributeId());
            }
        }
    }

    // ==================== 读：属性定义 ====================

    @Override
    public List<ProductAttribute> listDefinitions(Long categoryId, Integer type) {
        if (categoryId == null) {
            return Collections.emptyList();
        }
        LambdaQueryWrapper<ProductAttribute> w = new LambdaQueryWrapper<>();
        w.eq(ProductAttribute::getCategoryId, categoryId);
        if (type != null) {
            w.eq(ProductAttribute::getType, type);
        }
        w.orderByAsc(ProductAttribute::getSort).orderByAsc(ProductAttribute::getId);
        return productAttributeMapper.selectList(w);
    }

    @Override
    public List<ProductAttribute> listDefinitionsByProduct(Long productId, Integer type) {
        return listDefinitions(categoryIdOfProduct(productId), type);
    }

    // ==================== 读：属性值 ====================

    @Override
    public List<AttributeItemVO> listProductParams(Long productId) {
        if (productId == null) {
            return Collections.emptyList();
        }
        List<ProductAttributeValue> rows = productAttributeValueMapper.selectList(
                new LambdaQueryWrapper<ProductAttributeValue>()
                        .eq(ProductAttributeValue::getProductId, productId));
        if (rows.isEmpty()) {
            return Collections.emptyList();
        }
        Map<Long, ProductAttribute> defs = loadDefs(rows.stream()
                .map(ProductAttributeValue::getAttributeId).collect(Collectors.toSet()));

        List<AttributeItemVO> out = new ArrayList<>();
        for (ProductAttributeValue row : rows) {
            ProductAttribute def = defs.get(row.getAttributeId());
            if (def == null) {
                continue;   // 属性定义被删了 → 孤儿值，不外泄
            }
            AttributeItemVO vo = new AttributeItemVO();
            vo.setAttributeId(def.getId());
            vo.setName(def.getName());
            vo.setValue(row.getValue());
            out.add(vo);
        }
        out.sort(Comparator.comparingInt((AttributeItemVO vo) -> sortOf(defs.get(vo.getAttributeId()))));
        return out;
    }

    @Override
    public List<SpecOptionVO> listSpecOptions(Long productId) {
        if (productId == null) {
            return Collections.emptyList();
        }
        List<Long> skuIds = skuMapper.selectList(
                        new LambdaQueryWrapper<Sku>().eq(Sku::getProductId, productId))
                .stream().map(Sku::getId).collect(Collectors.toList());
        if (skuIds.isEmpty()) {
            return Collections.emptyList();
        }
        List<SkuAttributeValue> rows = skuAttributeValueMapper.selectList(
                new LambdaQueryWrapper<SkuAttributeValue>()
                        .in(SkuAttributeValue::getSkuId, skuIds));
        if (rows.isEmpty()) {
            return Collections.emptyList();
        }
        Map<Long, ProductAttribute> defs = loadDefs(rows.stream()
                .map(SkuAttributeValue::getAttributeId).collect(Collectors.toSet()));

        // LinkedHashSet 去重同时保留「首次出现顺序」，最后再按属性 sort 统一重排
        Map<Long, LinkedHashSet<String>> grouped = new LinkedHashMap<>();
        for (SkuAttributeValue row : rows) {
            if (row.getValue() == null || row.getValue().isEmpty() || !defs.containsKey(row.getAttributeId())) {
                continue;
            }
            grouped.computeIfAbsent(row.getAttributeId(), k -> new LinkedHashSet<>()).add(row.getValue());
        }

        List<SpecOptionVO> out = new ArrayList<>();
        for (Map.Entry<Long, LinkedHashSet<String>> entry : grouped.entrySet()) {
            ProductAttribute def = defs.get(entry.getKey());
            out.add(new SpecOptionVO(def.getId(), def.getName(), new ArrayList<>(entry.getValue())));
        }
        out.sort(Comparator.comparingInt((SpecOptionVO vo) -> sortOf(defs.get(vo.getAttributeId()))));
        return out;
    }

    // ==================== 读：按规格筛选（P2） ====================

    @Override
    public SpecMatchVO matchProductsBySpecs(Long categoryId, Map<String, List<String>> specs) {
        if (categoryId == null || specs == null || specs.isEmpty()) {
            return SpecMatchVO.empty();
        }

        // ① 属性名 → attribute_id。用 Map 承接而不是直接建 List<SpecQueryGroup>，顺带解决两件事：
        //    · 重复属性名（?attrs=颜色:黑色,颜色:蓝色）自动合并为一组；
        //    · 保证 groupCount == 实际组数 —— 一旦对不上，HAVING 恒不成立、静默返回空，极难排查。
        Map<Long, LinkedHashSet<String>> byAttrId = new LinkedHashMap<>();
        for (Map.Entry<String, List<String>> entry : specs.entrySet()) {
            String name = entry.getKey() == null ? "" : entry.getKey().trim();
            if (name.isEmpty() || entry.getValue() == null || entry.getValue().isEmpty()) {
                continue;
            }
            // 🔴 必须用**只读**的 selectByName，绝不能复用 resolveSpecAttributeId ——
            //    那个方法查不到会「自动建属性定义」。筛选是读路径，不该被一个拼错的属性名写脏数据。
            ProductAttribute def = selectByName(categoryId, name);
            if (def == null || def.getType() == null || def.getType() != ProductAttribute.TYPE_SPEC) {
                // 属性名不存在、或它是参数(type=1) —— 都不可能有商品命中，直接空结果（不报错）
                log.info("规格筛选：分类 {} 下不存在规格属性「{}」，返回空结果", categoryId, name);
                return SpecMatchVO.empty();
            }
            LinkedHashSet<String> values = byAttrId.computeIfAbsent(def.getId(), k -> new LinkedHashSet<>());
            for (String v : entry.getValue()) {
                if (v != null && !v.isBlank()) {
                    values.add(v.trim());
                }
            }
        }
        byAttrId.values().removeIf(Set::isEmpty);
        if (byAttrId.isEmpty()) {
            return SpecMatchVO.empty();
        }

        // ② 反查命中 SKU：组间 AND、组内 OR，走 sku_attribute_value.idx_attr_value
        List<SpecQueryGroup> groups = new ArrayList<>(byAttrId.size());
        for (Map.Entry<Long, LinkedHashSet<String>> entry : byAttrId.entrySet()) {
            groups.add(new SpecQueryGroup(entry.getKey(), new ArrayList<>(entry.getValue())));
        }
        List<Long> skuIds = skuAttributeValueMapper.selectSkuIdsBySpecGroups(groups, groups.size());
        if (skuIds.isEmpty()) {
            return SpecMatchVO.empty();
        }

        // ③ SKU → 商品ID + 最低价。
        //    最低价只取「命中规格的这批 SKU」（验收 #8），不是商品全局最低价 ——
        //    否则筛「容量=256G」时列表还显示 128G 的价，点进去对不上。
        List<Sku> skus = skuMapper.selectBatchIds(skuIds);
        Map<Long, BigDecimal> minPriceByProduct = new LinkedHashMap<>();
        for (Sku sku : skus) {
            if (sku.getProductId() == null || sku.getPrice() == null) {
                continue;
            }
            minPriceByProduct.merge(sku.getProductId(), sku.getPrice(), BigDecimal::min);
        }
        if (minPriceByProduct.isEmpty()) {
            return SpecMatchVO.empty();
        }
        return new SpecMatchVO(new ArrayList<>(minPriceByProduct.keySet()), minPriceByProduct);
    }

    @Override
    public List<SpecFacetVO> listSpecFacets(Long categoryId) {
        if (categoryId == null) {
            return Collections.emptyList();
        }
        // 只有 type=0（规格）才有 SKU 级取值可筛；参数(type=1)是商品级、不参与筛选
        List<ProductAttribute> defs = listDefinitions(categoryId, ProductAttribute.TYPE_SPEC);
        if (defs.isEmpty()) {
            return Collections.emptyList();
        }
        List<SpecFacetCount> counts = skuAttributeValueMapper.selectFacetCounts(categoryId,
                defs.stream().map(ProductAttribute::getId).collect(Collectors.toList()));

        Map<Long, List<SpecFacetValueVO>> byAttr = new HashMap<>();
        for (SpecFacetCount c : counts) {
            if (c.getValue() == null || c.getValue().isEmpty()) {
                continue;
            }
            SpecFacetValueVO vo = new SpecFacetValueVO();
            vo.setValue(c.getValue());
            vo.setCount(c.getProductCount() == null ? 0 : c.getProductCount());
            byAttr.computeIfAbsent(c.getAttributeId(), k -> new ArrayList<>()).add(vo);
        }

        List<SpecFacetVO> out = new ArrayList<>(defs.size());
        for (ProductAttribute def : defs) {          // defs 已按 sort、id 排序
            List<SpecFacetValueVO> values = byAttr.get(def.getId());
            if (values == null || values.isEmpty()) {
                continue;    // 该属性下没有已上架商品命中 → 整个属性不展示，避免「点了必然为空」
            }
            // 命中商品数倒序；并列时按取值升序 —— 顺序必须稳定，否则前端每刷一次都跳，也没法写断言
            values.sort(Comparator
                    .comparingInt((SpecFacetValueVO v) -> v.getCount() == null ? 0 : v.getCount())
                    .reversed()
                    .thenComparing(SpecFacetValueVO::getValue));
            SpecFacetVO vo = new SpecFacetVO();
            vo.setAttributeId(def.getId());
            vo.setName(def.getName());
            vo.setValues(values);
            out.add(vo);
        }
        return out;
    }

    // ==================== 内部工具 ====================

    /** sp_data 里的一条规格（key=属性名，value=取值） */
    private record SpecPair(String key, String value) {
    }

    private Long categoryIdOfProduct(Long productId) {
        if (productId == null) {
            return null;
        }
        Product product = productMapper.selectById(productId);
        return product == null ? null : product.getCategoryId();
    }

    private Map<Long, ProductAttribute> loadDefs(Set<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            return Collections.emptyMap();
        }
        return productAttributeMapper.selectBatchIds(ids).stream()
                .collect(Collectors.toMap(ProductAttribute::getId, a -> a, (a, b) -> a));
    }

    private int sortOf(ProductAttribute def) {
        return def == null || def.getSort() == null ? 0 : def.getSort();
    }

    /**
     * 取规格属性定义的 id；不存在则**自动创建**。
     * 自动建是为了让存量 SKU 与「运营没先配属性就直接加 SKU」都不被卡住。
     */
    private Long resolveSpecAttributeId(Long categoryId, String name) {
        ProductAttribute existing = selectByName(categoryId, name);
        if (existing != null) {
            return existing.getId();
        }
        ProductAttribute created = new ProductAttribute();
        created.setCategoryId(categoryId);
        created.setName(name);
        created.setType(ProductAttribute.TYPE_SPEC);
        created.setInputType(1);   // 规格天然是「从候选值里选一个」
        created.setSort(0);
        try {
            productAttributeMapper.insert(created);
            log.info("自动创建规格属性定义：categoryId={} name={} id={}", categoryId, name, created.getId());
            return created.getId();
        } catch (DuplicateKeyException e) {
            // 并发下另一事务刚建好 → 回查一次
            ProductAttribute again = selectByName(categoryId, name);
            return again == null ? null : again.getId();
        }
    }

    private ProductAttribute selectByName(Long categoryId, String name) {
        return productAttributeMapper.selectOne(
                new LambdaQueryWrapper<ProductAttribute>()
                        .eq(ProductAttribute::getCategoryId, categoryId)
                        .eq(ProductAttribute::getName, name));
    }

    /**
     * 把新出现的规格取值追加到候选值清单（管理端下拉用）。
     * 只增不删 —— 不覆盖运营手工整理过的清单。
     */
    private void appendInputList(Long attributeId, String value) {
        if (attributeId == null || value == null || value.isEmpty()) {
            return;
        }
        ProductAttribute def = productAttributeMapper.selectById(attributeId);
        if (def == null) {
            return;
        }
        String cur = def.getInputList() == null ? "" : def.getInputList();
        // ⚠️ 必须按逗号切开做**精确**比较，不能用 cur.contains(value)：
        //    文本 "128G" 恰好是 "5128G" 的子串，contains 会把新值误判成已存在。
        List<String> items = cur.isEmpty()
                ? new ArrayList<>()
                : new ArrayList<>(Arrays.asList(cur.split(",")));
        if (items.contains(value)) {
            return;
        }
        items.add(value);
        String joined = String.join(",", items);
        if (joined.length() > MAX_INPUT_LIST_LEN) {
            // 超列宽就放弃追加：不能因为候选值清单满了就让整次 SKU 保存回滚
            log.warn("属性 {} 候选值清单已达 {} 字符，未追加「{}」", attributeId, MAX_INPUT_LIST_LEN, value);
            return;
        }
        def.setInputList(joined);
        productAttributeMapper.updateById(def);
    }

    /**
     * 解析 sp_data。字段名同时兼容 key/name 与 value/val —— 与前端
     * portal-web/src/utils/spec.ts 的容错口径保持一致，避免两边判定不同步。
     */
    private List<SpecPair> parseSpecs(String spData) {
        List<SpecPair> out = new ArrayList<>();
        if (spData == null || spData.isBlank()) {
            return out;
        }
        String text = spData.trim();
        if ("[]".equals(text)) {
            return out;
        }
        try {
            JsonNode root = objectMapper.readTree(text);
            if (root == null || !root.isArray()) {
                return out;
            }
            for (JsonNode node : root) {
                String key = firstText(node, "key", "name");
                String value = firstText(node, "value", "val");
                if (key != null && !key.isBlank() && value != null && !value.isBlank()) {
                    out.add(new SpecPair(key.trim(), value.trim()));
                }
            }
        } catch (JsonProcessingException e) {
            // 前端 spec.ts 对非法 JSON 的兜底是「原样显示」；这里同理：不同步、不报错。
            // 若在此抛异常，运营存的畸形 sp_data 会让整次 SKU 保存失败，体验更差。
            log.warn("sp_data 不是合法 JSON，跳过规格同步：{}", text);
        }
        return out;
    }

    private String firstText(JsonNode node, String... fields) {
        for (String field : fields) {
            JsonNode v = node.get(field);
            if (v != null && !v.isNull()) {
                String s = v.asText();
                if (s != null && !s.isBlank()) {
                    return s;
                }
            }
        }
        return null;
    }
}
