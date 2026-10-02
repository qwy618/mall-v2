package com.macro.mall.admin.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.List;

@Data
public class UmsAdminDTO {
    private Long id;
    @NotBlank(message = "用户名不能为空")
    private String username;
    /** 新建必填；编辑时留空 = 不修改密码 */
    private String password;
    private String nickName;
    private String email;
    /** 1-启用 0-禁用 */
    private Integer status;
    /** 预留（实际分配角色走 /admin/role/update） */
    private List<Long> roleIds;
}
