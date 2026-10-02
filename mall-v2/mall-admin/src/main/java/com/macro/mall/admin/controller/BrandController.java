package com.macro.mall.admin.controller;
import com.macro.mall.admin.dto.BrandParam;
import com.macro.mall.admin.service.BrandService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.Brand;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;


@RestController
@RequestMapping("/brand")
public class BrandController {
    @Autowired
    private BrandService brandService;
    //分页查询
    @GetMapping("/list")
    public CommonResult<CommonPage<Brand>> list(@RequestParam Integer pageNum, @RequestParam Integer pageSize){
       return CommonResult.success(CommonPage.restPage(brandService.list(pageNum, pageSize)));
    }

    @GetMapping("/{id}")
    public CommonResult<Brand> getItem(@PathVariable Long id){
        return CommonResult.success(brandService.getItem(id));
    }
    @PostMapping("/create")
    public CommonResult<Long> create(@RequestBody@Valid BrandParam brandParam){
        return CommonResult.success(brandService.create(brandParam));
    }

    //更新品牌
    @PostMapping("/update/{id}")
    public CommonResult<Long> update(@PathVariable Long id, @RequestBody @Valid BrandParam brandParam) {
        return CommonResult.success(brandService.update(id, brandParam));
    }

    //删除品牌
    @PostMapping("/delete/{id}")
    public CommonResult<Long> delete(@PathVariable Long id) {
        return CommonResult.success(brandService.delete(id));
    }
}
