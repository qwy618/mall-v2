package com.macro.mall.portal.component;

import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.portal.component.MemberDetails;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;

/**
 * 从 SecurityContext 取当前登录会员ID（不信任前端传入）。
 * 会员端各 Controller 统一复用，避免重复解析鉴权逻辑。
 */
@Component
public class MemberAuth {

    /** 当前登录会员的 id；未登录抛 BusinessException */
    public Long memberId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof MemberDetails)) {
            throw new BusinessException("请先登录");
        }
        return ((MemberDetails) auth.getPrincipal()).getMember().getId();
    }
}
