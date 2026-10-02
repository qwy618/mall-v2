package com.macro.mall.admin.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class OrderShipParam {
    @NotBlank(message = "物流公司不能为空") private String deliveryCompany;
    @NotBlank(message = "物流单号不能为空") private String deliverySn;
}
