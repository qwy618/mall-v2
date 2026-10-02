package com.macro.mall.admin.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class CouponParam {
    @NotBlank(message = "券名称不能为空")
    private String name;
    @NotNull(message = "减免金额不能为空")
    private BigDecimal amount;
    private BigDecimal minPoint;   // 门槛，可不传（默认0）
    @NotNull(message = "使用类型不能为空")
    private Integer useType;       // 0/1/2
    private Long categoryId;       // useType=1 时填
    private Long productId;        // useType=2 时填
    @NotNull(message = "每人限领不能为空")
    private Integer perLimit;
    @NotNull(message = "发放总数不能为空")
    private Integer publishCount;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
    private String note;
}
