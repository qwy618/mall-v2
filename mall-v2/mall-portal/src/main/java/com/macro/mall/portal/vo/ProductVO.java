package com.macro.mall.portal.vo;

import com.macro.mall.mbg.model.Product;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 商品列表/详情展示用 VO。
 * SPU 表本身不存售价，售价在 SKU 表，这里携带「SKU 最低价」供前端展示。
 */
@Data
public class ProductVO {
    private Long id;
    private String productSn;
    private String name;
    private String pic;
    private Integer sale;
    private Integer status;
    /** SKU 最低价；该商品无 SKU 时为 null */
    private BigDecimal lowestPrice;

    public static ProductVO from(Product p, BigDecimal lowestPrice) {
        if (p == null) {
            return null;
        }
        ProductVO vo = new ProductVO();
        vo.setId(p.getId());
        vo.setProductSn(p.getProductSn());
        vo.setName(p.getName());
        vo.setPic(p.getPic());
        vo.setSale(p.getSale());
        vo.setStatus(p.getStatus());
        vo.setLowestPrice(lowestPrice);
        return vo;
    }
}
