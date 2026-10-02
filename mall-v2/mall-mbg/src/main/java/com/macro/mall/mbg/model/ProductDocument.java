package com.macro.mall.mbg.model;

import lombok.Data;
import java.io.Serializable;
import java.time.format.DateTimeFormatter;

@Data
public class ProductDocument implements Serializable {
    private static final long serialVersionUID = 1L;

    private Long id;
    private String productSn;
    private String name;
    private String subTitle;
    private Long brandId;
    private Long categoryId;
    private String pic;
    private Integer sale;
    private Integer status;
    /** 创建时间：字符串对齐 ES date 映射，避免 Jackson 序列化 LocalDateTime 失败 */
    private String createTime;

    public static ProductDocument convert(Product p) {
        ProductDocument doc = new ProductDocument();
        doc.setId(p.getId());
        doc.setProductSn(p.getProductSn());
        doc.setName(p.getName());
        doc.setSubTitle(p.getSubTitle());
        doc.setBrandId(p.getBrandId());
        doc.setCategoryId(p.getCategoryId());
        doc.setPic(p.getPic());
        doc.setSale(p.getSale());
        doc.setStatus(p.getStatus());
        if (p.getCreateTime() != null) {
            doc.setCreateTime(p.getCreateTime()
                    .format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        }
        return doc;
    }
}
