package com.macro.mall.portal.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.macro.mall.mbg.mapper.MemberMapper;
import com.macro.mall.mbg.model.Member;
import com.macro.mall.portal.component.MemberDetails;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

@Service
public class MemberDetailsServiceImpl implements UserDetailsService {
    private final MemberMapper memberMapper;

    public MemberDetailsServiceImpl(MemberMapper memberMapper) {
        this.memberMapper = memberMapper;
    }

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        // token 中存的是手机号，这里按 phone 查会员
        Member member = memberMapper.selectOne(
                new LambdaQueryWrapper<Member>().eq(Member::getPhone, username)
        );
        if (member == null) {
            throw new UsernameNotFoundException("会员不存在");
        }
        return new MemberDetails(member);
    }
}
