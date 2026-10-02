package com.macro.mall.admin.controller;

import com.macro.mall.admin.dto.CommentReplyParam;
import com.macro.mall.admin.service.CommentService;
import com.macro.mall.admin.vo.CommentListItemVO;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * 商品评价管理接口（后台）。受 MenuPermissionInterceptor 的 /comment→Comment 菜单鉴权保护。
 */
@RestController
@RequestMapping("/comment")
public class CommentController {

    @Autowired
    private CommentService commentService;

    @GetMapping("/list")
    public CommonResult<CommonPage<CommentListItemVO>> list(
            @RequestParam(value = "pageNum", defaultValue = "1") Integer pageNum,
            @RequestParam(value = "pageSize", defaultValue = "10") Integer pageSize,
            @RequestParam(value = "productId", required = false) Long productId,
            @RequestParam(value = "status", required = false) Integer status,
            @RequestParam(value = "keyword", required = false) String keyword) {
        return commentService.list(pageNum, pageSize, productId, status, keyword);
    }

    @PostMapping("/audit/{id}")
    public CommonResult<Void> audit(@PathVariable Long id,
                                   @RequestParam Integer status) {
        return commentService.audit(id, status);
    }

    @PostMapping("/reply/{id}")
    public CommonResult<Void> reply(@PathVariable Long id,
                                   @RequestBody CommentReplyParam param) {
        return commentService.reply(id, param.getReplyContent());
    }

    @PostMapping("/delete/{id}")
    public CommonResult<Void> delete(@PathVariable Long id) {
        return commentService.delete(id);
    }
}
