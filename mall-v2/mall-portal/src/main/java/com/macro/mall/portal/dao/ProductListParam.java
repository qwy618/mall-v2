package com.macro.mall.portal.dao;

import lombok.Data;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * C 端商品列表的查询条件（GET /product/list）。
 *
 * <p>抽成一个对象、而不是把一排 {@code @RequestParam} 堆在 Controller 签名上，
 * 是因为「规格筛选」需要一个解析落点：把 {@code attrs} 字符串拆成「属性名 → 选中值」
 * 再交给 mall-service（那里只认结构化入参，不关心分隔符）。
 * Spring 对 GET 查询参数会自动绑定到本对象的字段，缺省值由字段初始值兜底。
 */
@Data
public class ProductListParam {

    private String keyword;

    private Long categoryId;

    private Long brandId;

    /**
     * 规格筛选，格式 {@code 属性名:值|值,属性名:值}，例：{@code 颜色:黑色|白色,容量:256GB}。
     * 语义：跨属性 AND（黑色 且 256GB）、同属性多值 OR（黑色 或 白色）。不传 / 空串 = 不筛选。
     *
     * <p>⚠️ 取值里不能出现 {@code ,} {@code |} {@code :} 这三个分隔符
     * （全角 ｜／： 不在此列 —— 库里真有取值带全角 {@code ｜}，别顺手把它也替换掉）。
     * 这条约束与 {@code product_attribute.input_list} 的「逗号分隔」是同一条。
     */
    private String attrs;

    private Integer pageNum = 1;

    private Integer pageSize = 10;

    /** 最多允许几个规格组、每组最多几个取值 —— 防构造超长 SQL（超出的直接忽略，不报错） */
    private static final int MAX_GROUPS = 8;
    private static final int MAX_VALUES_PER_GROUP = 20;

    /**
     * 解析 attrs → 属性名 → 选中值（LinkedHashMap，顺序稳定便于测试）。
     *
     * <p>容错口径：空白段、没有 {@code :} 的段、属性名或值为空的段一律跳过，**不抛异常** ——
     * attrs 是前端拼出来的，格式错了顶多「这次不筛」，不该让整个列表页 500。
     * 重复的属性名在这里合并，避免后端 HAVING 的组数阈值与实际组数对不上（那会静默返回空结果）。
     *
     * @return 属性名 → 选中值；无有效条件时返回空 Map
     */
    public Map<String, List<String>> parseSpecs() {
        Map<String, List<String>> out = new LinkedHashMap<>();
        if (attrs == null || attrs.isBlank()) {
            return out;
        }
        for (String segment : attrs.split(",")) {
            int idx = segment.indexOf(':');
            if (idx <= 0) {
                continue;   // 没有属性名（或属性名为空）→ 跳过这一段
            }
            String name = segment.substring(0, idx).trim();
            String rawValues = segment.substring(idx + 1);
            if (name.isEmpty() || rawValues.isBlank()) {
                continue;
            }
            if (!out.containsKey(name) && out.size() >= MAX_GROUPS) {
                continue;   // 规格组数到上限：新属性名不再收（已在 Map 里的组仍可继续加值）
            }
            List<String> values = out.computeIfAbsent(name, k -> new ArrayList<>());
            for (String v : rawValues.split("\\|")) {
                String value = v.trim();
                if (value.isEmpty() || values.contains(value)) {
                    continue;
                }
                if (values.size() >= MAX_VALUES_PER_GROUP) {
                    break;
                }
                values.add(value);
            }
        }
        out.values().removeIf(List::isEmpty);
        return out;
    }
}
