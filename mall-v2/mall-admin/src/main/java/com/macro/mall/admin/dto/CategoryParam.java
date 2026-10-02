package com.macro.mall.admin.dto;


import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class CategoryParam {
    @NotBlank(message = "分类名称不能为空")
    private String name;
    @NotNull(message = "分类父ID不能为空")
    @Min(value = 0, message = "分类父ID不能小于0")
    private Long parentId;
    @NotNull(message = "分类级别不能为空")
    @Min(value = 0, message = "分类级别不能小于0")
    private Integer level;
    @NotNull(message = "分类排序不能为空")
    @Min(value = 0, message = "分类排序不能小于0")
    private Integer sort;
    @Size(max=255)
    private String icon;
    @NotNull(message = "分类显示状态不能为空")
    @Min(value = 0, message = "分类显示状态不能小于0")
    private Integer showStatus;
}
