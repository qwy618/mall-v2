package com.macro.mall.admin.controller;

import com.macro.mall.admin.service.DashboardService;
import com.macro.mall.admin.vo.DashboardStatsVO;
import com.macro.mall.admin.vo.DashboardTrendVO;
import com.macro.mall.common.CommonResult;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/admin/dashboard")
public class DashboardController {
    @Autowired
    private DashboardService dashboardService;

    @GetMapping("/stats")
    public CommonResult<DashboardStatsVO> stats() {
        return dashboardService.getStats();
    }

    @GetMapping("/trend")
    public CommonResult<DashboardTrendVO> trend(@RequestParam(defaultValue = "7") int days) {
        return dashboardService.getTrend(days);
    }
}
