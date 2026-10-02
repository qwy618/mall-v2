package com.macro.mall.admin.controller;

import com.macro.mall.admin.dto.OrderParam;
import com.macro.mall.admin.dto.OrderShipParam;
import com.macro.mall.admin.service.OrderService;
import com.macro.mall.admin.vo.OrderDetailVO;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.Order;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/order")
public class OrderController {
    @Autowired
    private OrderService orderService;
    //1.创建订单
    @PostMapping("/create")
    public CommonResult<Long> createOrder(@RequestBody @Valid OrderParam param) {
        return orderService.createOrder(param);
    }
    //2.查询订单
    @GetMapping("/list")
    public CommonResult<CommonPage<Order>> listOrders(@RequestParam Integer pageNum, @RequestParam Integer pageSize,
                                                      @RequestParam(required = false) Integer status, @RequestParam(required = false) Long memberId,
                                                      @RequestParam(required = false) String keyword) {
        return orderService.listOrders(pageNum, pageSize, status, memberId, keyword);
    }
    //3.查询订单详情
    @GetMapping("/{id}")
    public CommonResult<OrderDetailVO> detail(@PathVariable Long id) {
        return orderService.detail(id);
    }
    //4.支付
    @PostMapping("/pay/{id}")
    public CommonResult<Long> pay(@PathVariable Long id) {
        return orderService.pay(id);
    }
    //5.发货
    @PostMapping("/ship/{id}")
    public CommonResult<Long> ship(@PathVariable Long id, @RequestBody @Valid OrderShipParam param) {
        return orderService.ship(id, param);
    }
    //6.确认收货
    @PostMapping("/complete/{id}")
    public CommonResult<Long> complete(@PathVariable Long id) {
        return orderService.complete(id);
    }
    //7.取消订单
    @PostMapping("/cancel/{id}")
    public CommonResult<Long> cancel(@PathVariable Long id) {
        return orderService.cancel(id);
    }
    //7.1 作废订单（状态 5=无效订单）：已付款未发货，回滚库存/退券/退积分/退款
    @PostMapping("/invalidate/{id}")
    public CommonResult<Long> invalidate(@PathVariable Long id,
                                         @RequestParam(required = false) String note) {
        return orderService.invalidate(id, note);
    }
    //8.删除订单（逻辑删）
    @PostMapping("/delete/{id}")
    public CommonResult<Long> delete(@PathVariable Long id) {
        return orderService.delete(id);
    }

}
