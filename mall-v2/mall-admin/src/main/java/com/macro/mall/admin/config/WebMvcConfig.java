package com.macro.mall.admin.config;

import com.macro.mall.admin.component.MenuPermissionInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    private final MenuPermissionInterceptor menuPermissionInterceptor;

    public WebMvcConfig(MenuPermissionInterceptor menuPermissionInterceptor) {
        this.menuPermissionInterceptor = menuPermissionInterceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(menuPermissionInterceptor)
                .addPathPatterns("/**")
                .excludePathPatterns(
                        "/admin/login",          // 任何人都要调
                        "/admin/info",           // 任何人都要调
                        "/error",
                        "/**/*.css",
                        "/**/*.js",
                        "/**/*.png",
                        "/**/*.jpg",
                        "/**/*.ico",
                        "/favicon.ico",
                        "/swagger-ui/**",
                        "/v3/api-docs/**",
                        "/doc.html",
                        "/ws/**"
                );
    }
}
