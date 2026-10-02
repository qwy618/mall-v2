package com.macro.mall.portal.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 开启 Spring 定时任务（债务11：订单自动确认收货）。
 *
 * <p>此前项目里没有定时任务，超时取消走的是 RabbitMQ 延迟队列（TTL 30 分钟）；
 * 「发货 N 天后自动确认收货」的量级是天，用队列级 TTL 不合适，故改用 @Scheduled 定期扫描。
 */
@Configuration
@EnableScheduling
public class SchedulingConfig {
}
