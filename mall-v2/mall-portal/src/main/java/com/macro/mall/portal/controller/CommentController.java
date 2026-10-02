package com.macro.mall.portal.controller;

import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.portal.component.MemberDetails;
import com.macro.mall.portal.dao.CommentSubmitParam;
import com.macro.mall.portal.service.CommentService;
import com.macro.mall.portal.vo.CommentStatsVO;
import com.macro.mall.portal.vo.ProductCommentVO;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

/**
 * 商品评价接口（C 端）。
 * 除商品列表 / 统计（公开）外，提交与「我的评价」需登录。
 */
@RestController
@RequestMapping("/comment")
public class CommentController {

    @Autowired
    private CommentService commentService;

    @PostMapping("/submit")
    public CommonResult<Void> submit(@Valid @RequestBody CommentSubmitParam param) {
        return commentService.submit(currentMemberId(), param);
    }

    @GetMapping("/product/{productId}")
    public CommonResult<CommonPage<ProductCommentVO>> listProductComments(
            @PathVariable Long productId,
            @RequestParam(value = "pageNum", defaultValue = "1") Integer pageNum,
            @RequestParam(value = "pageSize", defaultValue = "10") Integer pageSize) {
        return commentService.listProductComments(productId, pageNum, pageSize);
    }

    @GetMapping("/product/{productId}/stats")
    public CommonResult<CommentStatsVO> getStats(@PathVariable Long productId) {
        return commentService.getStats(productId);
    }

    @GetMapping("/mine")
    public CommonResult<CommonPage<ProductCommentVO>> listMine(
            @RequestParam(value = "pageNum", defaultValue = "1") Integer pageNum,
            @RequestParam(value = "pageSize", defaultValue = "10") Integer pageSize) {
        return commentService.listMine(currentMemberId(), pageNum, pageSize);
    }

    /** 从 SecurityContext 取当前登录会员ID，不信任前端传入 */
    private Long currentMemberId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof MemberDetails)) {
            throw new com.macro.mall.common.exception.BusinessException("请先登录");
        }
        return ((MemberDetails) auth.getPrincipal()).getMember().getId();
    }
}
