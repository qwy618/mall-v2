package com.macro.mall.portal.config;

import com.macro.mall.common.mq.ProductMqConstants;
import org.springframework.amqp.core.*;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.HashMap;
import java.util.Map;

@Configuration
public class RabbitMQConfig {

    @Bean
    public DirectExchange delayExchange() {
        return ExchangeBuilder.directExchange(MqConstants.DELAY_EXCHANGE).durable(true).build();
    }

    @Bean
    public Queue delayQueue() {
        Map<String, Object> args = new HashMap<>();
        args.put("x-message-ttl", MqConstants.ORDER_TTL);                  // 队列级 TTL：30 分钟
        args.put("x-dead-letter-exchange", MqConstants.DEAD_EXCHANGE);      // 到期后转到的死信交换机
        args.put("x-dead-letter-routing-key", MqConstants.DEAD_ROUTING_KEY);
        return QueueBuilder.durable(MqConstants.DELAY_QUEUE).withArguments(args).build();
    }

    @Bean
    public Binding delayBinding() {
        return BindingBuilder.bind(delayQueue()).to(delayExchange()).with(MqConstants.DELAY_ROUTING_KEY);
    }

    @Bean
    public DirectExchange deadExchange() {
        return ExchangeBuilder.directExchange(MqConstants.DEAD_EXCHANGE).durable(true).build();
    }

    @Bean
    public Queue deadQueue() {
        return QueueBuilder.durable(MqConstants.DEAD_QUEUE).build();
    }

    @Bean
    public Binding deadBinding() {
        return BindingBuilder.bind(deadQueue()).to(deadExchange()).with(MqConstants.DEAD_ROUTING_KEY);
    }

    @Bean public DirectExchange productSyncExchange() {
        return ExchangeBuilder.directExchange(ProductMqConstants.EXCHANGE).durable(true).build();
    }
    @Bean public Queue productSyncQueue() {
        return QueueBuilder.durable(ProductMqConstants.QUEUE).build();
    }
    @Bean public Binding productSyncBinding() {
        return BindingBuilder.bind(productSyncQueue()).to(productSyncExchange()).with(ProductMqConstants.KEY);
    }
}
