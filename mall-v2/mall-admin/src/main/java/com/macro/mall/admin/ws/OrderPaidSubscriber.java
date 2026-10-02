package com.macro.mall.admin.ws;

import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class OrderPaidSubscriber implements MessageListener {

    @Override
    public void onMessage(Message message, byte[] pattern) {
        try {
            String body = new String(message.getBody());
            // 包装成 {type:'NEW_ORDER', payload:{...}} 推给前端
            String push = "{\"type\":\"NEW_ORDER\",\"payload\":" + body + "}";
            AdminWsHandler.broadcast(push);
        } catch (Exception e) {
            log.warn("处理新订单消息失败：{}", e.getMessage());
        }
    }
}
