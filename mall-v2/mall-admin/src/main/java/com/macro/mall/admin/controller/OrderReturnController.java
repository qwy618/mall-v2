package com.macro.mall.admin.controller;

import com.macro.mall.admin.service.OrderReturnService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.OrderReturnApply;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/order/return")
public class OrderReturnController {

    @Autowired
    private OrderReturnService orderReturnService;

    @GetMapping("/list")
    public CommonResult<CommonPage<OrderReturnApply>> list(
            @RequestParam(required = false) Integer status,
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize) {
        return orderReturnService.list(status, pageNum, pageSize);
    }

    @GetMapping("/{id}")
    public CommonResult<OrderReturnApply> detail(@PathVariable Long id) {
        return orderReturnService.detail(id);
    }

    @PostMapping("/approve/{id}")
    public CommonResult<Long> approve(@PathVariable Long id,
                                     @RequestParam(required = false) String handleNote,
                                     @RequestParam String companyAddress) {
        return orderReturnService.approve(id, handleNote, companyAddress);
    }

    @PostMapping("/reject/{id}")
    public CommonResult<Long> reject(@PathVariable Long id,
                                    @RequestParam(required = false) String handleNote) {
        return orderReturnService.reject(id, handleNote);
    }

    @PostMapping("/receive/{id}")
    public CommonResult<Long> receive(@PathVariable Long id) {
        return orderReturnService.receive(id);
    }

    @PostMapping("/complete/{id}")
    public CommonResult<Long> complete(@PathVariable Long id,
                                      @RequestParam(required = false) String handleNote) {
        return orderReturnService.complete(id, handleNote);
    }
}
