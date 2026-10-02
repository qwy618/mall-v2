package com.macro.mall.admin.controller;

import com.macro.mall.admin.service.CouponHistoryService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.CouponHistory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/couponHistory")
public class CouponHistoryController {
    @Autowired
    private CouponHistoryService couponHistoryService;

    @PostMapping("/receive")
    public CommonResult<Long> receive(@RequestParam Long couponId,
                                      @RequestParam Long memberId) {
        return couponHistoryService.receive(couponId, memberId);
    }
    @PostMapping("/use")
    public CommonResult<Void> use(@RequestParam Long historyId,
                                  @RequestParam Long orderId,
                                  @RequestParam String orderSn) {
        return couponHistoryService.use(historyId, orderId, orderSn);
    }
    @GetMapping("/listByMember")
    public CommonResult<List<CouponHistory>> listByMember(@RequestParam Long memberId,
                                                          @RequestParam(required = false) Integer status) {
        return couponHistoryService.listByMember(memberId, status);
    }
    @GetMapping("/list")
    public CommonResult<CommonPage<CouponHistory>> listHistories(@RequestParam Long couponId,
                                                                 @RequestParam(defaultValue = "1") Integer pageNum,
                                                                 @RequestParam(defaultValue = "10") Integer pageSize) {
        return couponHistoryService.listHistories(couponId, pageNum, pageSize);
    }

}
