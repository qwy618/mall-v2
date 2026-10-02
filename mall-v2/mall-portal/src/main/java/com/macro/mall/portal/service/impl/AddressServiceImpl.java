package com.macro.mall.portal.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.MemberAddressMapper;
import com.macro.mall.mbg.model.MemberAddress;
import com.macro.mall.portal.service.AddressService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class AddressServiceImpl implements AddressService {

    @Autowired
    private MemberAddressMapper addressMapper;

    @Override
    public List<MemberAddress> list(Long memberId) {
        LambdaQueryWrapper<MemberAddress> w = new LambdaQueryWrapper<>();
        w.eq(MemberAddress::getMemberId, memberId)
                .orderByDesc(MemberAddress::getDefaultStatus)
                .orderByAsc(MemberAddress::getId);
        return addressMapper.selectList(w);
    }

    @Override
    @Transactional
    public CommonResult<Void> add(Long memberId, MemberAddress address) {
        address.setId(null);
        address.setMemberId(memberId);   // 强制归属当前会员，不信任前端
        address.setCreateTime(null);     // 交给 DB 默认值
        address.setUpdateTime(null);
        // 该会员首个地址自动设为默认
        long count = addressMapper.selectCount(new LambdaQueryWrapper<MemberAddress>()
                .eq(MemberAddress::getMemberId, memberId));
        if (address.getDefaultStatus() == null) {
            address.setDefaultStatus(count == 0 ? 1 : 0);
        }
        addressMapper.insert(address);
        if (address.getDefaultStatus() == 1) {
            clearOtherDefault(memberId, address.getId());
        }
        return CommonResult.success(null);
    }

    @Override
    @Transactional
    public CommonResult<Void> update(Long memberId, MemberAddress address) {
        if (address.getId() == null) {
            throw new BusinessException("地址ID不能为空");
        }
        MemberAddress existing = addressMapper.selectById(address.getId());
        if (existing == null || !memberId.equals(existing.getMemberId())) {
            throw new BusinessException("地址不存在");
        }
        address.setMemberId(memberId);   // 防越权，强制覆盖
        address.setCreateTime(null);     // 不改创建时间
        address.setUpdateTime(null);     // 交给 DB
        if (address.getDefaultStatus() != null && address.getDefaultStatus() == 1) {
            clearOtherDefault(memberId, address.getId());
        }
        addressMapper.updateById(address);
        return CommonResult.success(null);
    }

    @Override
    @Transactional
    public CommonResult<Void> delete(Long memberId, Long id) {
        MemberAddress existing = addressMapper.selectById(id);
        if (existing == null || !memberId.equals(existing.getMemberId())) {
            throw new BusinessException("地址不存在");
        }
        boolean wasDefault = existing.getDefaultStatus() != null && existing.getDefaultStatus() == 1;
        addressMapper.deleteById(id);    // 物理删（member_address 无 delete_status 列）
        // 删掉的是默认地址且仍有其它地址，则把剩余第一个设为默认
        if (wasDefault) {
            long remain = addressMapper.selectCount(new LambdaQueryWrapper<MemberAddress>()
                    .eq(MemberAddress::getMemberId, memberId));
            if (remain > 0) {
                MemberAddress first = addressMapper.selectOne(new LambdaQueryWrapper<MemberAddress>()
                        .eq(MemberAddress::getMemberId, memberId)
                        .orderByAsc(MemberAddress::getId)
                        .last("LIMIT 1"));
                if (first != null) {
                    first.setDefaultStatus(1);
                    addressMapper.updateById(first);
                }
            }
        }
        return CommonResult.success(null);
    }

    @Override
    @Transactional
    public CommonResult<Void> setDefault(Long memberId, Long id) {
        MemberAddress existing = addressMapper.selectById(id);
        if (existing == null || !memberId.equals(existing.getMemberId())) {
            throw new BusinessException("地址不存在");
        }
        clearOtherDefault(memberId, id);
        LambdaUpdateWrapper<MemberAddress> set = new LambdaUpdateWrapper<>();
        set.eq(MemberAddress::getId, id)
                .eq(MemberAddress::getMemberId, memberId)
                .set(MemberAddress::getDefaultStatus, 1);
        addressMapper.update(null, set);
        return CommonResult.success(null);
    }

    /** 把该会员除 excludeId 外的地址默认标记清零（保证同一会员只有一个默认） */
    private void clearOtherDefault(Long memberId, Long excludeId) {
        LambdaUpdateWrapper<MemberAddress> clear = new LambdaUpdateWrapper<>();
        clear.eq(MemberAddress::getMemberId, memberId)
                .ne(MemberAddress::getId, excludeId)
                .set(MemberAddress::getDefaultStatus, 0);
        addressMapper.update(null, clear);
    }
}
