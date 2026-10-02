package com.macro.mall;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 后台管理启动类
 *
 * 坑位提示（阶段 2 最常踩的两个）：
 * 1. 启动类必须放在 com.macro.mall 而不是 com.macro.mall.admin，
 *    否则默认的包扫描路径扫不到 mall-common 里的 @RestControllerAdvice，全局异常处理器会失效。
 * 2. @MapperScan 要指向 mall-mbg 模块的 mapper 包，跨模块不会自动扫描。
 */
@MapperScan("com.macro.mall.mbg.mapper")
@SpringBootApplication(scanBasePackages = "com.macro.mall")
public class MallAdminApplication {

    public static void main(String[] args) {
        SpringApplication.run(MallAdminApplication.class, args);
    }
}
