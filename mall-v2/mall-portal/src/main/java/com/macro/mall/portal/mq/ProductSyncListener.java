package com.macro.mall.portal.mq;

import com.macro.mall.common.mq.ProductMqConstants;
import com.macro.mall.mbg.mapper.ProductMapper;
import com.macro.mall.mbg.model.Product;
import com.macro.mall.portal.search.EsProductService;
import com.rabbitmq.client.Channel;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;
import org.springframework.amqp.core.Message;
import java.io.IOException;


@Slf4j
@Component
@RequiredArgsConstructor
public class ProductSyncListener {
    private final EsProductService esProductService;
    private final ProductMapper productMapper;

    @RabbitListener(queues = ProductMqConstants.QUEUE, ackMode = "MANUAL")
    public void onMessage(Message message, Channel channel) throws IOException {
        long tag = message.getMessageProperties().getDeliveryTag();
        try {
            String[] p = new String(message.getBody()).trim().split(":");
            Long productId = Long.valueOf(p[0]);
            String action = p[1];
            if ("DELETE".equals(action)) {
                esProductService.delete(productId);
            } else { // CREATE / UPDATE
                Product product = productMapper.selectById(productId);
                if (product != null) esProductService.upsert(product);
                else esProductService.delete(productId); // 极端：已物理删则确保索引无残留
            }
            channel.basicAck(tag, false);
        } catch (Exception e) {
            log.error("商品同步失败 body={}", new String(message.getBody()), e);
            channel.basicNack(tag, false, false);
        }
    }
}

