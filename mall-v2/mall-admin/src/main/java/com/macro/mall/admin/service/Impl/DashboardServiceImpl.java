package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.macro.mall.admin.service.DashboardService;
import com.macro.mall.admin.vo.DashboardStatsVO;
import com.macro.mall.admin.vo.DashboardTrendVO;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.mapper.*;
import com.macro.mall.mbg.model.CouponHistory;
import com.macro.mall.mbg.model.Order;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class DashboardServiceImpl implements DashboardService {
    @Autowired
    private ProductMapper productMapper;
    @Autowired
    private OrderMapper orderMapper;
    @Autowired
    private BrandMapper brandMapper;
    @Autowired
    private CategoryMapper categoryMapper;
    @Autowired
    private CouponMapper couponMapper;
    @Autowired
    private CouponHistoryMapper couponHistoryMapper;

        @Override
        public CommonResult<DashboardStatsVO> getStats() {
            DashboardStatsVO vo = new DashboardStatsVO();

            vo.setProductTotal(productMapper.selectCount(new LambdaQueryWrapper<>()));

            vo.setOrderTotal(orderMapper.selectCount(new LambdaQueryWrapper<>()));

            LocalDateTime todayStart = LocalDate.now().atStartOfDay();
            vo.setOrderToday(orderMapper.selectCount(
                    new LambdaQueryWrapper<Order>().ge(Order::getCreateTime, todayStart)));

            vo.setBrandTotal(brandMapper.selectCount(new LambdaQueryWrapper<>()));
            vo.setCategoryTotal(categoryMapper.selectCount(new LambdaQueryWrapper<>()));
            vo.setCouponTotal(couponMapper.selectCount(new LambdaQueryWrapper<>()));

            vo.setCouponReceived(couponHistoryMapper.selectCount(new LambdaQueryWrapper<>()));
            vo.setCouponUsed(couponHistoryMapper.selectCount(
                    new LambdaQueryWrapper<CouponHistory>().eq(CouponHistory::getStatus, 1)));

            return CommonResult.success(vo);
        }

        @Override
        public CommonResult<DashboardTrendVO> getTrend(int days) {
            if (days <= 0) days = 7;
            if (days > 90) days = 90;

            // 窗口起点：days-1 天前的 00:00（含今天共 days 天）
            LocalDateTime start = LocalDate.now().minusDays(days - 1L).atStartOfDay();
            List<Map<String, Object>> rows = orderMapper.selectTrend(start);

            // 按天归集：count 与 amount
            Map<LocalDate, Long> countMap = new HashMap<>();
            Map<LocalDate, BigDecimal> amountMap = new HashMap<>();
            for (Map<String, Object> r : rows) {
                LocalDate d = toLocalDate(r.get("order_date"));
                if (d == null) continue;
                long cnt = ((Number) r.get("order_count")).longValue();
                BigDecimal amt = (BigDecimal) r.get("order_amount");
                countMap.put(d, cnt);
                amountMap.put(d, amt);
            }

            DashboardTrendVO vo = new DashboardTrendVO();
            vo.setDays(days);
            List<String> dateList = new ArrayList<>();
            List<Long> orderCounts = new ArrayList<>();
            List<BigDecimal> orderAmounts = new ArrayList<>();
            LocalDate today = LocalDate.now();
            for (int i = days - 1; i >= 0; i--) {
                LocalDate d = today.minusDays(i);
                dateList.add(String.format("%02d-%02d", d.getMonthValue(), d.getDayOfMonth()));
                orderCounts.add(countMap.getOrDefault(d, 0L));
                orderAmounts.add(amountMap.getOrDefault(d, BigDecimal.ZERO));
            }
            vo.setDateList(dateList);
            vo.setOrderCounts(orderCounts);
            vo.setOrderAmounts(orderAmounts);
            return CommonResult.success(vo);
        }

        /** 兼容 JDBC 返回的 java.sql.Date / LocalDateTime / 字符串，统一转 LocalDate */
        private LocalDate toLocalDate(Object o) {
            if (o == null) return null;
            if (o instanceof java.sql.Date) return ((java.sql.Date) o).toLocalDate();
            if (o instanceof LocalDateTime) return ((LocalDateTime) o).toLocalDate();
            if (o instanceof LocalDate) return (LocalDate) o;
            return LocalDate.parse(o.toString());
        }
    }

