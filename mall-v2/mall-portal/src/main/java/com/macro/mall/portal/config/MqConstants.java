package com.macro.mall.portal.config;

public final class MqConstants {
    private MqConstants() {}

    public static final String DELAY_EXCHANGE = "order.delay.exchange";
    public static final String DELAY_QUEUE = "order.delay.queue";
    public static final String DELAY_ROUTING_KEY = "order.delay.key";

    public static final String DEAD_EXCHANGE = "order.dead.exchange";
    public static final String DEAD_QUEUE = "order.dead.queue";
    public static final String DEAD_ROUTING_KEY = "order.dead.key";

    public static final long ORDER_TTL = 30 * 60 * 1000L; // 30 分钟
}
