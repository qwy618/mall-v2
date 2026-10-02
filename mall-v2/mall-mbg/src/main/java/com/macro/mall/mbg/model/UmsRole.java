package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("ums_role")
public class UmsRole {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private String name;        // 角色名称：超级管理员 / 商品管理员
    private String code;        // 角色标识：admin / product（给 hasRole 用）
    private String description;
    private Integer status;     // 1-启用 0-禁用
    private Integer sort;
    private String menuIds;
}
