package com.macro.mall.admin.service;

import com.macro.mall.admin.dto.OrderParam;
import com.macro.mall.admin.dto.OrderShipParam;
import com.macro.mall.admin.vo.OrderDetailVO;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.Order;
import jakarta.validation.Valid;


public interface OrderService  {
    CommonResult<Long> createOrder(OrderParam param);

    CommonResult<CommonPage<Order>> listOrders(Integer pageNum, Integer pageSize, Integer status, Long memberId, String keyword);

    CommonResult<OrderDetailVO> detail(Long id);

    CommonResult<Long> pay(Long id);

    CommonResult<Long> ship(Long id, @Valid OrderShipParam param);

    CommonResult<Long> complete(Long id);

    /** 作废订单（状态 5=无效订单）：仅已付款未发货可作废，回滚库存/退券/退积分/退款 */
    CommonResult<Long> invalidate(Long id, String note);

    CommonResult<Long> cancel(Long id);

    CommonResult<Long> delete(Long id);
}
