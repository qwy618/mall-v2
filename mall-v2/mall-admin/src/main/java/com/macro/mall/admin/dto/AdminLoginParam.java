package com.macro.mall.admin.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class AdminLoginParam {
    @NotBlank
    private String username;
    @NotBlank
    private String password;
}
