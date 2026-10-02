package com.macro.mall.admin.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class UpdateStatusParam {
    @NotNull(message = "状态不能为空")
    private Integer status;
}
