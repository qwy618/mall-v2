package com.macro.mall.admin.service;

import com.macro.mall.admin.dto.SkuParam;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.Sku;

public interface SkuService {
    CommonResult<CommonPage<Sku>> getList(Long productId, Integer pageNum, Integer pageSize);
    CommonResult<Sku> get(Long id);
    CommonResult<Long> create(SkuParam param);
    CommonResult<Long> update(Long id, SkuParam param);
    CommonResult<Long> delete(Long id);
}
