package com.macro.mall.portal.service.impl;

import com.aliyun.oss.OSS;
import com.aliyun.oss.model.ObjectMetadata;
import com.macro.mall.portal.service.OssService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

/**
 * 阿里云 OSS 上传实现（与 mall-admin 一致：UUID 文件名 + 后缀白名单）。
 */
@Service
public class OssServiceImpl implements OssService {

    private final OSS ossClient;

    @Value("${oss.bucket}") private String bucket;
    @Value("${oss.base-url}") private String baseUrl;

    public OssServiceImpl(OSS ossClient) {
        this.ossClient = ossClient;
    }

    // 允许的后缀白名单
    private static final String[] ALLOWED = {"jpg", "jpeg", "png", "webp"};

    @Override
    public String upload(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("文件为空");
        }
        String original = file.getOriginalFilename();
        String suffix = original == null ? "" :
                original.substring(original.lastIndexOf('.') + 1).toLowerCase();
        boolean ok = false;
        for (String a : ALLOWED) {
            if (a.equals(suffix)) { ok = true; break; }
        }
        if (!ok) {
            throw new IllegalArgumentException("仅支持 jpg / png / webp 格式");
        }

        String objectName = UUID.randomUUID().toString().replace("-", "") + "." + suffix;
        try {
            ObjectMetadata meta = new ObjectMetadata();
            meta.setContentType(file.getContentType());
            meta.setContentLength(file.getSize());
            ossClient.putObject(bucket, objectName, file.getInputStream(), meta);
        } catch (Exception e) {
            throw new RuntimeException("上传失败：" + e.getMessage(), e);
        }
        return baseUrl + "/" + objectName;
    }
}
