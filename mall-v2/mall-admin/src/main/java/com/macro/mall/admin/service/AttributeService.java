package com.macro.mall.admin.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.macro.mall.admin.dto.AttributeParam;
import com.macro.mall.mbg.model.ProductAttribute;
import com.macro.mall.service.vo.AttributeItemVO;

import java.util.List;

/**
 * 属性定义管理（债务 1，管理端）。属性值侧的读写复用 mall-service 的 ProductAttributeService。
 */
public interface AttributeService {

    IPage<ProductAttribute> list(Long categoryId, Integer type, Integer pageNum, Integer pageSize);

    /** 按商品取该商品所属分类下的属性定义（管理端 SKU 表单/参数表单用，不分页） */
    List<ProductAttribute> listByProduct(Long productId, Integer type);

    ProductAttribute getItem(Long id);

    Long create(AttributeParam param);

    Long update(Long id, AttributeParam param);

    Long delete(Long id);

    /** 某商品的参数（type=1） */
    List<AttributeItemVO> getProductParams(Long productId);

    /** 覆盖式保存某商品的参数（type=1，先清后插） */
    void saveProductParams(Long productId, List<AttributeItemVO> items);
}
