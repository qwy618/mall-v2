package com.macro.mall.admin.service;

import com.macro.mall.admin.vo.DashboardStatsVO;
import com.macro.mall.admin.vo.DashboardTrendVO;
import com.macro.mall.common.CommonResult;

public interface DashboardService {
    CommonResult<DashboardStatsVO> getStats();

    /**
     * 看板时序：最近 days 天（默认 7，上限 90）的每日订单数 + 销售额。
     */
    CommonResult<DashboardTrendVO> getTrend(int days);
}
