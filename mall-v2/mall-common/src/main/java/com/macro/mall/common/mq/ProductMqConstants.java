package com.macro.mall.common.mq;
public final class ProductMqConstants {
    private ProductMqConstants() {}
    public static final String EXCHANGE = "product.sync.exchange";
    public static final String QUEUE = "product.sync.queue";
    public static final String KEY = "product.sync.key";
}
