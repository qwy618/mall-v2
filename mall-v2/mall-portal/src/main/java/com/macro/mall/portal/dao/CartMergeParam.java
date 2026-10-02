package com.macro.mall.portal.dao;

import lombok.Data;

import java.io.Serializable;

/**
 * 未登录购物车合并入参：前端 localStorage 暂存车的单条（skuId + 数量）。
 * 登录成功后随 {@code POST /cart/merge} 批量提交，按 memberId 合并进会员购物车。
 */
@Data
public class CartMergeParam implements Serializable {
    private Long skuId;
    private Integer quantity;
}
