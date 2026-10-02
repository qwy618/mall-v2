package com.macro.mall.portal.service;

import com.macro.mall.mbg.model.Member;
import com.macro.mall.portal.vo.LoginResultVO;

public interface MemberService {
    /** 注册，返回新会员 id（phone 为登录名，唯一） */
    Long register(String phone, String password, String nickname);

    /** 登录，返回 JWT + 会员信息（不含密码） */
    LoginResultVO login(String phone, String password);

    /** 查当前会员（密码置空、手机号脱敏），用于个人中心 */
    Member getCurrentMember(String phone);

    /** 修改密码：校验旧密码、加密新密码落库 */
    void updatePassword(String phone, String oldPwd, String newPwd);

    /** 更新头像 URL（OSS 上传后写入 member.icon） */
    void updateIcon(String phone, String icon);

    /** 按 id 查会员（密码置空、手机号不脱敏，供等级/积分等内部接口使用） */
    Member getById(Long id);
}
