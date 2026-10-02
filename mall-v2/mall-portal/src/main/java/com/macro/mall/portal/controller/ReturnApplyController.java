package com.macro.mall.portal.controller;

import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.model.OrderReturnApply;
import com.macro.mall.portal.component.MemberDetails;
import com.macro.mall.portal.dao.ReturnApplyParam;
import com.macro.mall.portal.service.ReturnApplyService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/return")
public class ReturnApplyController {

    @Autowired
    private ReturnApplyService returnApplyService;

    @PostMapping("/apply")
    public CommonResult<Long> apply(@RequestBody ReturnApplyParam param) {
        return returnApplyService.apply(currentMemberId(), param);
    }

    @GetMapping("/list")
    public CommonResult<List<OrderReturnApply>> list() {
        return returnApplyService.list(currentMemberId());
    }

    @GetMapping("/detail/{id}")
    public CommonResult<OrderReturnApply> detail(@PathVariable Long id) {
        return returnApplyService.detail(currentMemberId(), id);
    }

    @PostMapping("/shipBack/{id}")
    public CommonResult<Long> shipBack(@PathVariable Long id, @RequestParam String returnTrackingNo) {
        return returnApplyService.shipBack(currentMemberId(), id, returnTrackingNo);
    }

    private Long currentMemberId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof MemberDetails)) {
            throw new BusinessException("请先登录");
        }
        return ((MemberDetails) auth.getPrincipal()).getMember().getId();
    }
}
