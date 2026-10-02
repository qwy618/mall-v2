package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.admin.dto.SkuParam;
import com.macro.mall.admin.service.SkuService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.mapper.SkuMapper;
import com.macro.mall.mbg.model.Sku;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

@Service
public class SkuServiceImpl implements SkuService {
    @Autowired
    private SkuMapper skuMapper;

    @Override
    public CommonResult<CommonPage<Sku>> getList(Long productId, Integer pageNum, Integer pageSize) {
        IPage<Sku> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<Sku> w = new LambdaQueryWrapper<>();
        w.eq(Sku::getProductId, productId);
        IPage<Sku> result = skuMapper.selectPage(page, w);
        return CommonResult.success(CommonPage.restPage(result));
    }

    @Override
    public CommonResult<Sku> get(Long id) {
        Sku sku = skuMapper.selectById(id);
        if (sku == null) {
            return CommonResult.failed("SKU不存在");
        }
        return CommonResult.success(sku);
    }

    @Override
    public CommonResult<Long> create(SkuParam param) {
        Sku sku = new Sku();
        BeanUtils.copyProperties(param, sku);
        sku.setSkuCode(genSkuCode());            // 决策①：后端生成唯一号
        if (sku.getStock() == null) sku.setStock(0);
        if (sku.getLockStock() == null) sku.setLockStock(0);
        if (sku.getSale() == null) sku.setSale(0);
        skuMapper.insert(sku);
        return CommonResult.success(sku.getId());
    }

    @Override
    public CommonResult<Long> update(Long id, SkuParam param) {
        Sku sku = skuMapper.selectById(id);
        if (sku == null) {
            return CommonResult.failed("SKU不存在");
        }
        BeanUtils.copyProperties(param, sku);
        int rows = skuMapper.updateById(sku);
        return CommonResult.success((long) rows);
    }

    @Override
    public CommonResult<Long> delete(Long id) {
        int rows = skuMapper.deleteById(id);     // sku 无 deleteStatus → 物理删除
        return CommonResult.success((long) rows);
    }

    private String genSkuCode() {
        return "S" + DateTimeFormatter.ofPattern("yyyyMMddHHmmssSSS").format(LocalDateTime.now())
                + (int) (Math.random() * 900 + 100);
    }
}
