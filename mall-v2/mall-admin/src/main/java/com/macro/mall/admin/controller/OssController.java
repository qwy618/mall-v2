package com.macro.mall.admin.controller;

import com.macro.mall.admin.service.OssService;
import com.macro.mall.common.CommonResult;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/oss")
public class OssController {

    private final OssService ossService;

    public OssController(OssService ossService) {
        this.ossService = ossService;
    }

    @PostMapping("/upload")
    public CommonResult<String> upload(@RequestParam("file") MultipartFile file) {
        return CommonResult.success(ossService.upload(file));
    }
}
