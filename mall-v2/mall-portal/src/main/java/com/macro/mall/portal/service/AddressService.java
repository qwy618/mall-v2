package com.macro.mall.portal.service;

import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.MemberAddress;

import java.util.List;

public interface AddressService {
    List<MemberAddress> list(Long memberId);
    CommonResult<Void> add(Long memberId, MemberAddress address);
    CommonResult<Void> update(Long memberId, MemberAddress address);
    CommonResult<Void> delete(Long memberId, Long id);
    CommonResult<Void> setDefault(Long memberId, Long id);
}
