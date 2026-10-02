package com.macro.mall.portal.component;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.macro.mall.mbg.mapper.OrderMapper;
import com.macro.mall.mbg.model.Order;
import com.macro.mall.portal.service.OrderService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 订单自动确认收货（债务11）：发货后满 N 天仍未确认收货，系统自动确认并赠送积分。
 *
 * <p>设计要点：
 * <ul>
 *   <li><b>起点用 delivery_time</b>（发货时间）而非 create_time——用户关心的是"到手多久"。</li>
 *   <li><b>幂等靠状态机</b>：真正的流转在 {@link OrderService#completeOrder} 里以
 *       原子条件 UPDATE(WHERE status=2) 完成，重复扫描 / 并发执行都只生效一次。</li>
 *   <li><b>单条失败不影响整批</b>：逐单 try-catch，避免一条脏数据导致整轮中断。</li>
 *   <li>每轮限量扫描，防止单次大事务拖垮数据库。</li>
 * </ul>
 *
 * <p>参数（可用 --mall.order.auto-confirm-* 覆盖，默认 7 天 / 10 分钟一轮）：
 * <pre>
 *   mall.order.auto-confirm-days              自动确认收货天数，默认 7
 *   mall.order.auto-confirm-batch             每轮最多处理单数，默认 200
 *   mall.order.auto-confirm-initial-delay-ms  启动后首次执行延迟，默认 60s
 *   mall.order.auto-confirm-interval-ms       两轮之间的间隔，默认 10min
 * </pre>
 */
@Component
@Slf4j
public class OrderAutoConfirmTask {

    private final OrderMapper orderMapper;
    private final OrderService orderService;

    @Value("${mall.order.auto-confirm-days:7}")
    private int autoConfirmDays;

    @Value("${mall.order.auto-confirm-batch:200}")
    private int batchSize;

    public OrderAutoConfirmTask(OrderMapper orderMapper, OrderService orderService) {
        this.orderMapper = orderMapper;
        this.orderService = orderService;
    }

    @Scheduled(initialDelayString = "${mall.order.auto-confirm-initial-delay-ms:60000}",
            fixedDelayString = "${mall.order.auto-confirm-interval-ms:600000}")
    public void autoConfirmExpiredOrders() {
        LocalDateTime deadline = LocalDateTime.now().minusDays(autoConfirmDays);
        List<Order> candidates = orderMapper.selectList(new LambdaQueryWrapper<Order>()
                .eq(Order::getStatus, 2)                 // 仅已发货
                .isNotNull(Order::getDeliveryTime)
                .le(Order::getDeliveryTime, deadline)    // 发货时间早于截止点
                .orderByAsc(Order::getDeliveryTime)
                .last("limit " + batchSize));
        if (candidates.isEmpty()) return;

        int done = 0;
        for (Order o : candidates) {
            try {
                if (orderService.completeOrder(o.getId(), "system")) {
                    done++;
                    log.info("订单 {} 发货超过 {} 天，已自动确认收货", o.getOrderSn(), autoConfirmDays);
                }
            } catch (Exception e) {
                log.error("自动确认收货失败 orderId={} orderSn={}", o.getId(), o.getOrderSn(), e);
            }
        }
        log.info("自动确认收货扫描完成：命中 {} 单，成功 {} 单（阈值 {} 天）",
                candidates.size(), done, autoConfirmDays);
    }
}
