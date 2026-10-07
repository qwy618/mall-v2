package com.macro.mall.mbg.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.macro.mall.mbg.dto.SpecFacetCount;
import com.macro.mall.mbg.dto.SpecQueryGroup;
import com.macro.mall.mbg.model.SkuAttributeValue;
import org.apache.ibatis.annotations.Param;

import java.util.List;

public interface SkuAttributeValueMapper extends BaseMapper<SkuAttributeValue> {

    /**
     * 按规格反查 SKU（P2 债务 2 —— 「按规格筛选」的核心）。
     *
     * 每个规格组展开成 `(attribute_id = ? AND value IN (...))`，组间 OR 连接；
     * 再按 sku_id 分组，用 `COUNT(DISTINCT attribute_id) = 组数` 实现「跨属性 AND」。
     *
     * ⚠️ 调用方必须保证 groups 非空、且每个组的 values 非空 —— 否则拼出的 SQL 语义会失真。
     *
     * @param groups     规格组（属性 + 选中值），组间 AND
     * @param groupCount 规格组个数，即 groups.size()（HAVING 的阈值，必须与 groups 一致）
     * @return 满足**全部**规格组的 SKU id
     */
    List<Long> selectSkuIdsBySpecGroups(@Param("groups") List<SpecQueryGroup> groups,
                                        @Param("groupCount") int groupCount);

    /**
     * 筛选面板（facet）：指定规格属性各取值命中的「已上架商品数」。
     *
     * @param categoryId   分类 id（必传；把 product 的访问钉在 idx_category_status 上）
     * @param attributeIds 该分类下 type=0 的属性 id（非空）
     * @return 每个 (attribute_id, value) 一行的命中商品数；没有商品命中的取值不会出现在结果里
     */
    List<SpecFacetCount> selectFacetCounts(@Param("categoryId") Long categoryId,
                                           @Param("attributeIds") List<Long> attributeIds);
}
