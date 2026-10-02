package com.macro.mall.portal.dao;

import lombok.Data;

import java.util.List;

@Data
public class ReturnApplyParam {
    private Long orderId;                 // 退哪笔订单（必须 status=3 已完成）
    private List<ApplyItem> items;        // 退货项列表（可部分退）
    private String reason;                // 退货原因
    private String description;           // 说明
    private List<String> proofPics;       // 凭证图 URL 列表
}
