package com.macro.mall.admin.service;

import com.macro.mall.admin.dto.ProductParam;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.Product;

public interface ProductService {
    CommonResult<CommonPage<Product>> getList(Integer pageNum, Integer pageSize, String keyword, Long brandId, Long categoryId, Integer status);

    CommonResult<Product> get(Long id);

    CommonResult<Long> create(ProductParam productParam);

    CommonResult<Long> update(Long id, ProductParam productParam);

    CommonResult<Long> delete(Long id);
}
