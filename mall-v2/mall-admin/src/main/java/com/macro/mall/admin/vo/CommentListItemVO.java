package com.macro.mall.admin.vo;

import lombok.Data;

import java.util.Date;

/**
 * 评价管理列表项 VO（后台）。
 */
@Data
public class CommentListItemVO {
    private Long id;
    private Long orderItemId;
    private Long orderId;
    private String orderSn;        // 便于定位来源订单
    private Long productId;
    private String productName;
    private String productPic;
    private Long memberId;
    private String nickname;
    private String icon;
    private Integer star;
    private Integer anonymous;
    private String content;
    private String pics;          // 晒图 JSON
    private Integer status;        // 0待审核 1通过 2驳回
    private String replyContent;
    private Date replyTime;
    private Date createTime;
}
