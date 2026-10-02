package com.macro.mall;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 会员端（C 端）启动类
 *
 * 关键：照搬 admin 的两处扫描策略，否则会踩同样的坑：
 * 1. scanBasePackages = "com.macro.mall" 才能扫到 mall-common 里的
 *    @RestControllerAdvice 全局异常处理器（BusinessException -> failed(msg)）。
 * 2. @MapperScan 指向 mall-mbg 的 mapper 包，跨模块不会自动扫描。
 */
@MapperScan("com.macro.mall.mbg.mapper")
@SpringBootApplication(scanBasePackages = "com.macro.mall")
public class MallPortalApplication {

    public static void main(String[] args) {
        SpringApplication.run(MallPortalApplication.class, args);
    }
}
