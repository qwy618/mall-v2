package com.macro.mall.portal.vo;

import lombok.Data;

import java.util.Date;

/**
 * 商品评价 VO（C 端公开列表 / 我的评价 共用）。
 * 匿名评价时 nickname/icon 置空，前端显示「匿名用户」。
 */
@Data
public class ProductCommentVO {
    private Long id;
    private Integer star;
    private String content;
    /** 晒图 JSON（与后端 comment.pics 一致，前端 toPics 兼容解析） */
    private String pics;
    /** 是否匿名：1 匿名 0 否 */
    private Integer anonymous;
    private String nickname;
    private String icon;
    private String replyContent;
    private Date replyTime;
    private Date createTime;
}
