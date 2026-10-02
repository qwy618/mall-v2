package com.macro.mall.admin.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.util.List;

@Data
public class RoleMenuUpdateParam {
    @NotNull(message = "角色ID不能为空")
    private Long roleId;
    /** 前端路由 name 列表；空集合 = 清除可见菜单 */
    private List<String> menuIds;
}
