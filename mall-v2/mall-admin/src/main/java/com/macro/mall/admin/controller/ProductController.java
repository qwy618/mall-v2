package com.macro.mall.admin.controller;

import com.macro.mall.admin.dto.ProductParam;
import com.macro.mall.admin.service.ProductService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.Product;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/product")
public class ProductController {
    @Autowired
    private ProductService productService;
    @GetMapping("/list")
    public CommonResult<CommonPage<Product>> getList(@RequestParam Integer pageNum, @RequestParam Integer pageSize,    @RequestParam(required = false) String keyword,
                                                     @RequestParam(required = false) Long brandId,
                                                     @RequestParam(required = false) Long categoryId,
                                                     @RequestParam(required = false) Integer status) {
        return productService.getList(pageNum, pageSize, keyword, brandId, categoryId, status);
    }
    @GetMapping("/{id}")
    public CommonResult<Product> getItem(@PathVariable Long id) {
        return productService.get(id);
    }
    @PostMapping("/create")
    public CommonResult<Long> create(@RequestBody @Valid ProductParam productParam) {
        return productService.create(productParam);
    }
    @PostMapping("/update/{id}")
    public CommonResult<Long> update(@PathVariable Long id, @RequestBody @Valid ProductParam productParam) {
        return productService.update(id, productParam);
    }
    @PostMapping("/delete/{id}")
    public CommonResult<Long> delete(@PathVariable Long id) {
        return productService.delete(id);
    }

}
