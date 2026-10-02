package com.macro.mall.portal.search;

import lombok.AllArgsConstructor;
import lombok.Data;

import java.util.List;

@Data
@AllArgsConstructor
public class EsSearchResult {
    private List<Long> ids;   // 按相关度排序的商品 id
    private long total;       // 命中总数
}
