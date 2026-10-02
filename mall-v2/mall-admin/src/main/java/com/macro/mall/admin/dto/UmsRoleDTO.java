package com.macro.mall.admin.dto;

import lombok.Data;

import java.util.List;

/** 角色新建/编辑入参（不含 menuIds，菜单单独走 /role/updateMenus） */
@Data
public class UmsRoleDTO {
    private Long id;
    private String name;
    private String code;
    private String description;
    private Integer status;
    private Integer sort;
}
