package com.macro.mall.admin.service;

import org.springframework.web.multipart.MultipartFile;

public interface OssService {
    /** 上传文件到 OSS，返回可访问的图片 URL */
    String upload(MultipartFile file);
}
