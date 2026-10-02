package com.macro.mall.portal.controller;

import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.MemberProductCollection;
import com.macro.mall.portal.component.MemberAuth;
import com.macro.mall.portal.service.CollectService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/member/collect")
public class CollectController {

    @Autowired
    private CollectService collectService;
    @Autowired
    private MemberAuth memberAuth;

    @PostMapping("/add")
    public CommonResult<Void> add(@RequestParam Long productId) {
        collectService.add(memberAuth.memberId(), productId);
        return CommonResult.success(null);
    }

    @PostMapping("/delete")
    public CommonResult<Void> delete(@RequestParam Long productId) {
        collectService.delete(memberAuth.memberId(), productId);
        return CommonResult.success(null);
    }

    @GetMapping("/list")
    public CommonResult<List<MemberProductCollection>> list() {
        return CommonResult.success(collectService.list(memberAuth.memberId()));
    }

    @GetMapping("/isCollected")
    public CommonResult<Boolean> isCollected(@RequestParam Long productId) {
        return CommonResult.success(collectService.isCollected(memberAuth.memberId(), productId));
    }
}
