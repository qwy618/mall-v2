package com.macro.mall.portal.search;

import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class EsDataInitializer implements CommandLineRunner {

    private final EsProductService esProductService;

    public EsDataInitializer(EsProductService esProductService) {
        this.esProductService = esProductService;
    }

    @Override
    public void run(String... args) {
//        try {
//            esProductService.createIndex();   // 已存在会抛异常，下面 catch 住
//        } catch (Exception e) {
//            log.info("product 索引已存在，跳过 createIndex");
//        }
        try {
            esProductService.importAll();
            log.info("ES 商品索引初始化完成");
        } catch (Exception e) {
            // ⚠️ 不要抛异常，否则应用起不来；ES 没起时只告警
            log.error("ES 商品索引导入失败（ES 可能未启动）：{}", e.getMessage());
        }
    }
}
