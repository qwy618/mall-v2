package com.macro.mall.portal.mq;

import com.macro.mall.portal.config.MqConstants;
import com.macro.mall.portal.service.impl.OrderServiceImpl;
import com.rabbitmq.client.Channel;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Slf4j
@Component
@RequiredArgsConstructor
public class OrderCancelListener {

    private final OrderServiceImpl orderService;

    @RabbitListener(queues = MqConstants.DEAD_QUEUE, ackMode = "MANUAL")
    public void onMessage(Message message, Channel channel) throws IOException {
        long deliveryTag = message.getMessageProperties().getDeliveryTag();
        try {
            Long orderId = Long.parseLong(new String(message.getBody()).trim());
            orderService.cancelExpiredBySystem(orderId); // 幂等取消
            channel.basicAck(deliveryTag, false);
        } catch (Exception e) {
            log.error("订单超时取消处理失败, body={}", new String(message.getBody()), e);
            channel.basicNack(deliveryTag, false, false); // 不重排，避免死循环
        }
    }
}
