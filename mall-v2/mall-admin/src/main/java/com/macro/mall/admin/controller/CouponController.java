package com.macro.mall.admin.controller;

import com.macro.mall.admin.dto.CouponParam;
import com.macro.mall.admin.service.CouponService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.Coupon;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/coupon")
public class CouponController {
    @Autowired
    private CouponService couponService;

    @GetMapping("/list")
    public CommonResult<CommonPage<Coupon>> list(
            @RequestParam(value = "pageNum", defaultValue = "1") Integer pageNum,
            @RequestParam(value = "pageSize", defaultValue = "10") Integer pageSize,
            @RequestParam(value = "useType", required = false) Integer useType,
            @RequestParam(value = "keyword", required = false) String keyword) {
        return couponService.listCoupons(pageNum, pageSize, useType, keyword);
    }
    @GetMapping("/{id}")
    public CommonResult<Coupon> detail(@PathVariable Long id) {
        return couponService.detail(id);
    }
    @PostMapping("/create")
    public CommonResult<Long> create(@Valid @RequestBody CouponParam param) {
        return couponService.createCoupon(param);
    }
    @PostMapping("/update/{id}")
    public CommonResult<Integer> update(@PathVariable Long id, @Valid @RequestBody CouponParam param) {
        return couponService.updateCoupon(id, param);
    }
    @PostMapping("/delete/{id}")
    public CommonResult<Integer> delete(@PathVariable Long id) {
        return couponService.deleteCoupon(id);
    }

}
