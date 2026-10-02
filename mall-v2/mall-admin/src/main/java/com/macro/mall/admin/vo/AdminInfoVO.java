package com.macro.mall.admin.vo;

import lombok.Data;

import java.util.List;

@Data                       // ← 必须加，生成 getter/setter
public class AdminInfoVO {  // ← 建议改名 AdminInfoVO，跟 AdminLoginVO 统一
    private String username;
    private String nickName;
    private String icon;
    private String email;
    private List<String> roles;
    private List<String> menuIds;
}
