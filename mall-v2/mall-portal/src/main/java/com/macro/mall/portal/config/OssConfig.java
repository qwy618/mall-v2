package com.macro.mall.portal.config;

import com.aliyun.oss.OSS;
import com.aliyun.oss.OSSClientBuilder;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 阿里云 OSS 客户端配置（C 端晒图上传复用，与 mall-admin 同一套凭据）。
 */
@Configuration
public class OssConfig {

    @Value("${oss.endpoint}") private String endpoint;
    @Value("${oss.access-key-id}") private String accessKeyId;
    @Value("${oss.access-key-secret}") private String accessKeySecret;

    @Bean
    public OSS ossClient() {
        return new OSSClientBuilder().build(endpoint, accessKeyId, accessKeySecret);
    }
}
