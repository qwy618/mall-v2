package com.macro.mall.admin.controller;

import com.macro.mall.admin.dto.CategoryParam;
import com.macro.mall.admin.service.CategoryService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.Category;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/category")
public class CategoryController {
    @Autowired
    private CategoryService categoryService;
    @GetMapping("/list")
    public CommonResult<CommonPage<Category>> list(@RequestParam Integer pageNum, @RequestParam Integer pageSize,@RequestParam(required = false) Integer parentId) {
        return CommonResult.success(CommonPage.restPage(categoryService.list(pageNum, pageSize, parentId)));
    }
    @GetMapping("/{id}")
    public CommonResult<Category> getItem(@PathVariable Long id) {
        return CommonResult.success(categoryService.getItem(id));
    }
    @PostMapping("/create")
    public CommonResult<Long> create(@RequestBody @Valid CategoryParam categoryParam) {
        return CommonResult.success(categoryService.create(categoryParam));
    }
    //更新
    @PostMapping("/update/{id}")
    public CommonResult update(@PathVariable Long id, @RequestBody @Valid CategoryParam categoryParam) {
        return CommonResult.success(categoryService.update(id, categoryParam));
    }
    //删除
    @PostMapping("/delete/{id}")
    public CommonResult delete(@PathVariable Long id) {
        return CommonResult.success(categoryService.delete(id));
    }
}
