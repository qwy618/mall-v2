package com.macro.mall.admin.vo;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

/** 管理员列表项：UmsAdmin 字段 + 角色 code 数组（前端 roles 直接渲染标签） */
@Data
public class AdminListItemVO {
    private Long id;
    private String username;
    private String nickName;
    private String icon;
    private String email;
    private Integer status;
    private LocalDateTime createTime;
    private List<String> roles;
}
