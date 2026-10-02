package com.macro.mall.admin.ws;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.util.concurrent.CopyOnWriteArrayList;

@Slf4j
@Component
public class AdminWsHandler extends TextWebSocketHandler {

    public static final CopyOnWriteArrayList<WebSocketSession> SESSIONS = new CopyOnWriteArrayList<>();

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        SESSIONS.add(session);
        log.info("WS 连接建立，当前在线管理员数：{}", SESSIONS.size());
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, org.springframework.web.socket.CloseStatus status) {
        SESSIONS.remove(session);
        log.info("WS 连接关闭，当前在线管理员数：{}", SESSIONS.size());
    }

    public static void broadcast(String message) {
        for (WebSocketSession session : SESSIONS) {
            if (session.isOpen()) {
                try {
                    session.sendMessage(new TextMessage(message));
                } catch (IOException e) {
                    SESSIONS.remove(session);
                }
            }
        }
    }
}
