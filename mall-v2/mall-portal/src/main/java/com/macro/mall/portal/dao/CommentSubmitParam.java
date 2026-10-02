package com.macro.mall.portal.dao;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.util.List;

/**
 * 提交评价入参（C 端）。按订单项粒度，一个订单里的每个商品各评一次。
 */
@Data
public class CommentSubmitParam {
    @NotNull(message = "订单项ID不能为空")
    private Long orderItemId;

    /** 整体单星评分 1-5 */
    @NotNull(message = "评分不能为空")
    private Integer star;

    /** 文字内容（可空） */
    private String content;

    /** 晒单图片 URL 列表（上传到 OSS 后回填） */
    private List<String> pics;

    /** 是否匿名：true 匿名，前端展示「匿名用户」 */
    private Boolean anonymous;
}
