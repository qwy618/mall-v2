package com.macro.mall.portal.controller;

import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.model.Order;
import com.macro.mall.portal.component.MemberDetails;
import com.macro.mall.portal.dao.CreateOrderParam;
import com.macro.mall.portal.service.OrderIdempotentService;
import com.macro.mall.portal.service.OrderService;
import com.macro.mall.portal.vo.OrderDetailVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/order")
public class OrderController {

    @Autowired
    private OrderService orderService;

    @Autowired
    private OrderIdempotentService orderIdempotentService;

    /** 下单幂等令牌（债务23）：进入确认订单页时取号，提交 /order/create 时原样带回 */
    @PostMapping("/token")
    public CommonResult<String> token() {
        return CommonResult.success(orderIdempotentService.generate(currentMemberId()));
    }

    @PostMapping("/create")
    public CommonResult<Long> create(@RequestBody CreateOrderParam param) {
        return orderService.createOrder(currentMemberId(), param);
    }

    @PostMapping("/pay")
    public CommonResult<Long> pay(@RequestParam Long orderId) {
        return orderService.pay(currentMemberId(), orderId);
    }

    @PostMapping("/cancel")
    public CommonResult<Long> cancel(@RequestParam Long orderId) {
        return orderService.cancel(currentMemberId(), orderId);
    }

    @PostMapping("/confirmReceived")
    public CommonResult<Long> confirmReceived(@RequestParam Long orderId) {
        return orderService.confirmReceived(currentMemberId(), orderId);
    }

    @GetMapping("/list")
    public CommonResult<CommonPage<Order>> list(@RequestParam(required = false) Integer status,
                                                @RequestParam(defaultValue = "1") Integer pageNum,
                                                @RequestParam(defaultValue = "10") Integer pageSize) {
        return orderService.listOrders(currentMemberId(), status, pageNum, pageSize);
    }

    @GetMapping("/detail")
    public CommonResult<OrderDetailVO> detail(@RequestParam Long orderId) {
        return orderService.detail(currentMemberId(), orderId);
    }

    private Long currentMemberId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof MemberDetails)) {
            throw new BusinessException("请先登录");
        }
        return ((MemberDetails) auth.getPrincipal()).getMember().getId();
    }
}
