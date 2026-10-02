package com.macro.mall.portal.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.MemberMapper;
import com.macro.mall.mbg.model.Member;
import com.macro.mall.portal.component.JwtTokenUtil;
import com.macro.mall.portal.service.MemberService;
import com.macro.mall.portal.vo.LoginResultVO;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class MemberServiceImpl implements MemberService {

    private final MemberMapper memberMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenUtil jwtTokenUtil;

    public MemberServiceImpl(MemberMapper memberMapper,
                             PasswordEncoder passwordEncoder,
                             JwtTokenUtil jwtTokenUtil) {
        this.memberMapper = memberMapper;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenUtil = jwtTokenUtil;
    }

    @Override
    public Long register(String phone, String password, String nickname) {
        if (memberMapper.selectCount(new LambdaQueryWrapper<Member>()
                .eq(Member::getPhone, phone)) > 0) {
            throw new BusinessException("手机号已注册");
        }
        Member m = new Member();
        m.setPhone(phone);
        m.setPassword(passwordEncoder.encode(password));
        m.setNickname(nickname);
        m.setStatus(1);
        memberMapper.insert(m);
        return m.getId();
    }

    @Override
    public LoginResultVO login(String phone, String password) {
        Member m = memberMapper.selectOne(new LambdaQueryWrapper<Member>()
                .eq(Member::getPhone, phone));
        if (m == null) {
            throw new BusinessException("用户不存在");
        }
        if (m.getStatus() != null && m.getStatus() == 0) {
            throw new BusinessException("账号已禁用");
        }
        if (!passwordEncoder.matches(password, m.getPassword())) {
            throw new BusinessException("密码错误");
        }
        String token = jwtTokenUtil.generateToken(m.getPhone());
        // 密码绝不返回前端
        m.setPassword(null);
        LoginResultVO vo = new LoginResultVO();
        vo.setToken(token);
        vo.setMember(m);
        return vo;
    }

    @Override
    public Member getCurrentMember(String phone) {
        Member m = memberMapper.selectOne(new LambdaQueryWrapper<Member>()
                .eq(Member::getPhone, phone));
        if (m == null) {
            throw new BusinessException("账号异常");
        }
        m.setPassword(null);
        m.setPhone(maskPhone(m.getPhone()));
        return m;
    }

    @Override
    public void updatePassword(String phone, String oldPwd, String newPwd) {
        Member m = memberMapper.selectOne(new LambdaQueryWrapper<Member>()
                .eq(Member::getPhone, phone));
        if (m == null) {
            throw new BusinessException("账号异常");
        }
        if (!passwordEncoder.matches(oldPwd, m.getPassword())) {
            throw new BusinessException("原密码错误");
        }
        if (newPwd == null || newPwd.length() < 6 || newPwd.length() > 20) {
            throw new BusinessException("新密码长度需为 6-20 位");
        }
        if (passwordEncoder.matches(newPwd, m.getPassword())) {
            throw new BusinessException("新密码不能与原密码相同");
        }
        m.setPassword(passwordEncoder.encode(newPwd));
        memberMapper.updateById(m);
    }

    @Override
    public void updateIcon(String phone, String icon) {
        Member m = memberMapper.selectOne(new LambdaQueryWrapper<Member>()
                .eq(Member::getPhone, phone));
        if (m == null) {
            throw new BusinessException("账号异常");
        }
        m.setIcon(icon);
        memberMapper.updateById(m);
    }

    @Override
    public Member getById(Long id) {
        Member m = memberMapper.selectById(id);
        if (m == null) {
            throw new BusinessException("账号异常");
        }
        m.setPassword(null);
        return m;
    }

    private String maskPhone(String phone) {
        if (phone == null || phone.length() < 7) {
            return phone;
        }
        return phone.substring(0, 3) + "****" + phone.substring(phone.length() - 4);
    }
}
