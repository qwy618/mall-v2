package com.macro.mall.portal.service;

import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.Order;
import com.macro.mall.portal.dao.CreateOrderParam;
import com.macro.mall.portal.dao.OrderPreviewParam;
import com.macro.mall.portal.vo.OrderDetailVO;
import com.macro.mall.portal.vo.OrderPreviewVO;

public interface OrderService {
    CommonResult<Long> createOrder(Long memberId, CreateOrderParam param);

    /**
     * 订单试算（债务：金额同源）：与 {@link #createOrder} 走**同一段金额计算**，
     * 但不扣库存、不落库、不消耗幂等令牌、不核销券、不扣积分。
     * 用于确认卡片 / 结算页展示「应付金额」，保证与最终下单逐分一致。
     */
    CommonResult<OrderPreviewVO> preview(Long memberId, OrderPreviewParam param);
    CommonResult<Long> pay(Long memberId, Long orderId);
    CommonResult<Long> cancel(Long memberId, Long orderId);
    CommonResult<Long> confirmReceived(Long memberId, Long orderId);

    /**
     * 订单完成（债务11）：原子把 已发货(2) 流转为 已完成(3) 并赠送积分/成长值。
     * 手动确认收货与「发货 N 天后自动确认收货」定时任务共用本方法，保证两条路径口径一致。
     *
     * @param operator 操作人（前台为「会员{id}」，定时任务为 system）
     * @return true=本次真的完成了订单；false=订单不存在或状态已不是已发货（幂等，重复调用安全）
     */
    boolean completeOrder(Long orderId, String operator);
    CommonResult<CommonPage<Order>> listOrders(Long memberId, Integer status, Integer pageNum, Integer pageSize);
    CommonResult<OrderDetailVO> detail(Long memberId, Long orderId);
}
