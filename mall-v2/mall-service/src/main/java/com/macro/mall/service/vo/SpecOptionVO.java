package com.macro.mall.service.vo;

import lombok.Data;

import java.util.List;

/**
 * 一个规格属性的可选值集合，如 { name: "颜色", values: ["黑色","白色"] }。
 * C 端详情页按属性名分组展示可选规格；P2「按规格筛选」也复用它。
 */
@Data
public class SpecOptionVO {
    private Long attributeId;
    private String name;
    private List<String> values;

    public SpecOptionVO() {
    }

    public SpecOptionVO(Long attributeId, String name, List<String> values) {
        this.attributeId = attributeId;
        this.name = name;
        this.values = values;
    }
}
