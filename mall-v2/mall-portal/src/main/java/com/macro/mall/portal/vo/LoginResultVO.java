package com.macro.mall.portal.vo;

import com.macro.mall.mbg.model.Member;
import lombok.Data;

@Data
public class LoginResultVO {
    private String token;
    private Member member;
}
