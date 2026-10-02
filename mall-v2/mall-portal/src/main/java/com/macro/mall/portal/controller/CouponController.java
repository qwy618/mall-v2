package com.macro.mall.portal.controller;

import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.model.Coupon;
import com.macro.mall.portal.component.MemberDetails;
import com.macro.mall.portal.dao.CouponEstimateParam;
import com.macro.mall.portal.service.CouponService;
import com.macro.mall.portal.vo.CouponEstimateVO;
import com.macro.mall.portal.vo.MyCouponVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/coupon")
public class CouponController {

    @Autowired
    private CouponService couponService;

    /** 可领取的优惠券列表（公开） */
    @GetMapping("/list")
    public CommonResult<List<Coupon>> list() {
        return CommonResult.success(couponService.listAvailable());
    }

    /** 领取优惠券（需登录）。从 JWT 解析出的会员身份取 memberId */
    @PostMapping("/receive")
    public CommonResult<Void> receive(@RequestParam Long couponId) {
        if(currentMemberId() == null){
            throw new BusinessException("请先登录");
        }
        return couponService.receive(currentMemberId(), couponId);
    }

    /** 我的券（需登录） */
    @GetMapping("/my")
    public CommonResult<List<MyCouponVO>> my() {
        if(currentMemberId() == null){
            throw new BusinessException("请先登录");
        }
        return CommonResult.success(couponService.myCoupons(currentMemberId()));
    }

    /** 预估可用券（确认订单页预览，需登录，只读不核销） */
    @PostMapping("/estimate")
    public CommonResult<List<CouponEstimateVO>> estimate(@RequestBody CouponEstimateParam param) {
        return CommonResult.success(couponService.estimate(currentMemberId(), param));
    }

    /** 从 SecurityContext 取出当前登录会员ID */
    private Long currentMemberId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof MemberDetails)) {
            throw new BusinessException("请先登录");
        }
        return ((MemberDetails) auth.getPrincipal()).getMember().getId();
    }
}
