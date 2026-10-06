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
import com.macro.mall.service.ProductAttributeService;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

@Service
public class SkuServiceImpl implements SkuService {
    @Autowired
    private SkuMapper skuMapper;

    /**
     * 跨端属性能力（mall-service）：把 sp_data 拆解成 sku_attribute_value 派生索引。
     * 债务 1 —— sp_data 仍是真源，这里只写索引，不改 sp_data。
     */
    @Autowired
    private ProductAttributeService productAttributeService;

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
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> create(SkuParam param) {
        Sku sku = new Sku();
        BeanUtils.copyProperties(param, sku);
        sku.setSkuCode(genSkuCode());            // 决策①：后端生成唯一号
        if (sku.getStock() == null) sku.setStock(0);
        if (sku.getLockStock() == null) sku.setLockStock(0);
        if (sku.getSale() == null) sku.setSale(0);
        skuMapper.insert(sku);
        // 债务1：同步规格派生索引。必须与 insert 同事务 —— 否则 SKU 建了、索引没建，
        // 或索引建了、SKU 回滚，两种都会让「按规格筛选」与商品对不上。
        productAttributeService.syncSkuSpecs(sku.getId(), sku.getSpData());
        return CommonResult.success(sku.getId());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> update(Long id, SkuParam param) {
        Sku sku = skuMapper.selectById(id);
        if (sku == null) {
            return CommonResult.failed("SKU不存在");
        }
        BeanUtils.copyProperties(param, sku);
        int rows = skuMapper.updateById(sku);
        productAttributeService.syncSkuSpecs(id, sku.getSpData());
        return CommonResult.success((long) rows);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> delete(Long id) {
        // sku 无 deleteStatus → 物理删除，派生索引不会跟着走，必须先手动清，
        // 否则 sku_attribute_value 留孤儿行，之后按规格筛选会翻出已删的 SKU
        productAttributeService.removeSkuSpecs(id);
        int rows = skuMapper.deleteById(id);
        return CommonResult.success((long) rows);
    }

    private String genSkuCode() {
        return "S" + DateTimeFormatter.ofPattern("yyyyMMddHHmmssSSS").format(LocalDateTime.now())
                + (int) (Math.random() * 900 + 100);
    }
}
