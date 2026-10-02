package com.macro.mall.portal.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.mapper.BrandMapper;
import com.macro.mall.mbg.mapper.ProductMapper;
import com.macro.mall.mbg.model.Brand;
import com.macro.mall.mbg.model.Product;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Objects;

@RestController
@RequestMapping("/brand")
public class BrandController {

    @Autowired
    private BrandMapper brandMapper;

    @Autowired
    private ProductMapper productMapper;

    /**
     * 品牌列表（按 sort 升序）。
     * 传入 categoryId 时，只返回该分类下存在商品的品牌；否则返回全部品牌。
     */
    @GetMapping("/list")
    public CommonResult<List<Brand>> list(@RequestParam(required = false) Long categoryId) {
        LambdaQueryWrapper<Brand> w = new LambdaQueryWrapper<>();
        w.orderByAsc(Brand::getSort);

        if (categoryId != null) {
            List<Long> brandIds = productMapper.selectList(
                            new LambdaQueryWrapper<Product>()
                                    .select(Product::getBrandId)
                                    .eq(Product::getCategoryId, categoryId))
                    .stream()
                    .map(Product::getBrandId)
                    .filter(Objects::nonNull)
                    .distinct()
                    .toList();
            if (brandIds.isEmpty()) {
                return CommonResult.success(new java.util.ArrayList<>());
            }
            w.in(Brand::getId, brandIds);
        }
        return CommonResult.success(brandMapper.selectList(w));
    }
}
