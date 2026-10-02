package com.macro.mall.admin.controller;

import com.macro.mall.admin.dto.SkuParam;
import com.macro.mall.admin.service.SkuService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.Sku;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/sku")
public class SkuController {
    @Autowired
    private SkuService skuService;

    @GetMapping("/list")
    public CommonResult<CommonPage<Sku>> getList(@RequestParam Long productId,
                                                 @RequestParam Integer pageNum,
                                                 @RequestParam Integer pageSize) {
        return skuService.getList(productId, pageNum, pageSize);
    }

    @GetMapping("/{id}")
    public CommonResult<Sku> getItem(@PathVariable Long id) {
        return skuService.get(id);
    }

    @PostMapping("/create")
    public CommonResult<Long> create(@RequestBody @Valid SkuParam param) {
        return skuService.create(param);
    }

    @PostMapping("/update/{id}")
    public CommonResult<Long> update(@PathVariable Long id, @RequestBody @Valid SkuParam param) {
        return skuService.update(id, param);
    }

    @PostMapping("/delete/{id}")
    public CommonResult<Long> delete(@PathVariable Long id) {
        return skuService.delete(id);
    }
}
