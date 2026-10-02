package com.macro.mall.portal.controller;

import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.portal.component.MemberDetails;
import com.macro.mall.portal.dao.CartMergeParam;
import com.macro.mall.portal.service.CartService;
import com.macro.mall.portal.vo.CartItemVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/cart")
public class CartController {

    @Autowired
    private CartService cartService;

    @PostMapping("/add")
    public CommonResult<Void> add(@RequestParam Long skuId,
                                  @RequestParam(defaultValue = "1") Integer quantity) {
        return cartService.add(currentMemberId(), skuId, quantity);
    }

    @PostMapping("/update")
    public CommonResult<Void> updateQuantity(@RequestParam Long cartItemId,
                                             @RequestParam Integer quantity) {
        return cartService.updateQuantity(currentMemberId(), cartItemId, quantity);
    }

    @DeleteMapping("/delete")
    public CommonResult<Void> delete(@RequestParam Long cartItemId) {
        return cartService.delete(currentMemberId(), cartItemId);
    }

    @PostMapping("/check")
    public CommonResult<Void> check(@RequestParam Long cartItemId,
                                    @RequestParam Integer checked) {
        return cartService.check(currentMemberId(), cartItemId, checked);
    }

    @GetMapping("/list")
    public CommonResult<List<CartItemVO>> list() {
        return cartService.list(currentMemberId());
    }

    /** 未登录购物车合并：登录成功后把 localStorage 暂存车批量合并进当前会员购物车 */
    @PostMapping("/merge")
    public CommonResult<Void> merge(@RequestBody List<CartMergeParam> items) {
        return cartService.merge(currentMemberId(), items);
    }

    /** 从 SecurityContext 取当前登录会员ID，不信任前端传入 */
    private Long currentMemberId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof MemberDetails)) {
            throw new BusinessException("请先登录");
        }
        return ((MemberDetails) auth.getPrincipal()).getMember().getId();
    }
}
