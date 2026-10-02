package com.macro.mall.portal.controller;

import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.MemberAddress;
import com.macro.mall.portal.component.MemberAuth;
import com.macro.mall.portal.service.AddressService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/member/address")
public class AddressController {

    @Autowired
    private AddressService addressService;
    @Autowired
    private MemberAuth memberAuth;

    @GetMapping("/list")
    public CommonResult<List<MemberAddress>> list() {
        return CommonResult.success(addressService.list(memberAuth.memberId()));
    }

    @PostMapping("/add")
    public CommonResult<Void> add(@RequestBody MemberAddress address) {
        return addressService.add(memberAuth.memberId(), address);
    }

    @PostMapping("/update")
    public CommonResult<Void> update(@RequestBody MemberAddress address) {
        return addressService.update(memberAuth.memberId(), address);
    }

    @PostMapping("/delete")
    public CommonResult<Void> delete(@RequestParam Long id) {
        return addressService.delete(memberAuth.memberId(), id);
    }

    @PostMapping("/setDefault")
    public CommonResult<Void> setDefault(@RequestParam Long id) {
        return addressService.setDefault(memberAuth.memberId(), id);
    }
}
