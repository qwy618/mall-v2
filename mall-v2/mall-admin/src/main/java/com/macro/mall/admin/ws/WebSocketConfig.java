package com.macro.mall.admin.ws;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private final AdminWsHandler adminWsHandler;

    public WebSocketConfig(AdminWsHandler adminWsHandler) {
        this.adminWsHandler = adminWsHandler;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(adminWsHandler, "/ws/admin")
                .setAllowedOriginPatterns("*");
    }
}
