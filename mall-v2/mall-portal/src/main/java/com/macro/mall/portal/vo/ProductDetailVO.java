package com.macro.mall.portal.vo;

import com.macro.mall.mbg.model.Sku;
import com.macro.mall.portal.vo.ProductVO;
import lombok.Data;

import java.util.List;

@Data
public class ProductDetailVO {
    private ProductVO product;
    private List<Sku> skus;
}
