package com.macro.mall.admin.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.util.List;

@Data
public class AdminRoleUpdateParam {
    @NotNull(message = "管理员ID不能为空")
    private Long adminId;
    @NotNull(message = "角色不能为空")
    private List<Long> roleIds;
}
