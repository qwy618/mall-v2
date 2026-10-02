package com.macro.mall.portal.service;

import org.springframework.web.multipart.MultipartFile;

/**
 * 文件上传到阿里云 OSS，返回可访问的图片 URL。
 */
public interface OssService {
    String upload(MultipartFile file);
}
