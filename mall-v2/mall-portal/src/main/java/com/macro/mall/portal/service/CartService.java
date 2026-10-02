package com.macro.mall.portal.service;

import com.macro.mall.common.CommonResult;
import com.macro.mall.portal.dao.CartMergeParam;
import com.macro.mall.portal.vo.CartItemVO;
import java.util.List;

public interface CartService {
    CommonResult<Void> add(Long memberId, Long skuId, Integer quantity);
    CommonResult<Void> updateQuantity(Long memberId, Long cartItemId, Integer quantity);
    CommonResult<Void> delete(Long memberId, Long cartItemId);
    CommonResult<Void> check(Long memberId, Long cartItemId, Integer checked);
    CommonResult<List<CartItemVO>> list(Long memberId);
    /** 未登录购物车合并：把前端 localStorage 暂存车按 memberId 合并进会员购物车 */
    CommonResult<Void> merge(Long memberId, List<CartMergeParam> items);
}
