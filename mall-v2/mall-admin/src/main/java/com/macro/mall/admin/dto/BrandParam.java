package com.macro.mall.admin.dto;


import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;


import java.time.LocalDateTime;

@Data
public class BrandParam {
    @NotBlank(message = "品牌名称不能为空")
    @Size(max=64)
    private String name;
    @Size(max=500)
    private String description;
    @Size(max=255)
    private String logo;
    @Min(0)
    private Integer sort;
}
