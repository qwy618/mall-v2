package com.macro.mall.portal.controller;

import com.macro.mall.common.CommonResult;
import com.macro.mall.portal.component.MemberDetails;
import com.macro.mall.portal.service.OssService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * C 端文件上传（晒图）。端点固定为 POST /upload，与前端 portal-web 的 uploadImage 对齐。
 * 复用阿里云 OSS，必须经会员登录（不能复用 admin 的 /oss/upload，后者受 admin 鉴权保护）。
 */
@RestController
@RequestMapping("/upload")
public class FileController {

    @Autowired
    private OssService ossService;

    @PostMapping
    public CommonResult<String> upload(@RequestParam("file") MultipartFile file) {
        // 校验登录态（匿名上传无意义，且防止滥用）
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof MemberDetails)) {
            return CommonResult.unauthorized("请先登录");
        }
        return CommonResult.success(ossService.upload(file));
    }
}
