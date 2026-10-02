package com.macro.mall.admin.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.util.List;

/**
 * 看板时序返回结构：最近 days 天的订单数 + 销售额。
 */
@Data
public class DashboardTrendVO {
    private Integer days;                // 统计窗口天数
    private List<String> dateList;       // 日期标签，如 ["09-17", "09-18", ...]
    private List<Long> orderCounts;      // 每日订单数（无订单为 0）
    private List<BigDecimal> orderAmounts; // 每日销售额（pay_amount 求和，无订单为 0）
}
