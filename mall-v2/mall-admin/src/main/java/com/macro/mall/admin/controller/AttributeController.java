package com.macro.mall.admin.controller;

import com.macro.mall.admin.dto.AttributeParam;
import com.macro.mall.admin.service.AttributeService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.ProductAttribute;
import com.macro.mall.service.vo.AttributeItemVO;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 属性管理（债务 1）。
 * 规格(type=0) 由 SKU 保存时从 sp_data 自动同步，不需要在这里单独维护取值；
 * 参数(type=1) 通过 /attribute/productParams 读写。
 */
@RestController
@RequestMapping("/attribute")
public class AttributeController {

    @Autowired
    private AttributeService attributeService;

    @GetMapping("/list")
    public CommonResult<CommonPage<ProductAttribute>> list(
            @RequestParam(required = false) Long categoryId,
            @RequestParam(required = false) Integer type,
            @RequestParam Integer pageNum,
            @RequestParam Integer pageSize) {
        return CommonResult.success(CommonPage.restPage(
                attributeService.list(categoryId, type, pageNum, pageSize)));
    }

    /** 按商品取属性定义（管理端 SKU 表单 / 参数表单的下拉用，不分页） */
    @GetMapping("/listByProduct")
    public CommonResult<List<ProductAttribute>> listByProduct(
            @RequestParam Long productId,
            @RequestParam(required = false) Integer type) {
        return CommonResult.success(attributeService.listByProduct(productId, type));
    }

    @GetMapping("/{id}")
    public CommonResult<ProductAttribute> getItem(@PathVariable Long id) {
        return CommonResult.success(attributeService.getItem(id));
    }

    @PostMapping("/create")
    public CommonResult<Long> create(@RequestBody @Valid AttributeParam param) {
        return CommonResult.success(attributeService.create(param));
    }

    @PostMapping("/update/{id}")
    public CommonResult<Long> update(@PathVariable Long id, @RequestBody @Valid AttributeParam param) {
        return CommonResult.success(attributeService.update(id, param));
    }

    @PostMapping("/delete/{id}")
    public CommonResult<Long> delete(@PathVariable Long id) {
        return CommonResult.success(attributeService.delete(id));
    }

    /** 某商品的参数值（type=1） */
    @GetMapping("/productParams")
    public CommonResult<List<AttributeItemVO>> getProductParams(@RequestParam Long productId) {
        return CommonResult.success(attributeService.getProductParams(productId));
    }

    /** 覆盖式保存某商品的参数值（type=1，先清后插） */
    @PostMapping("/productParams/{productId}")
    public CommonResult<Void> saveProductParams(@PathVariable Long productId,
                                                @RequestBody List<AttributeItemVO> items) {
        attributeService.saveProductParams(productId, items);
        return CommonResult.success(null);
    }
}
