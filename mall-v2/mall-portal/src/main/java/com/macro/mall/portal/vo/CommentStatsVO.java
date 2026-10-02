package com.macro.mall.portal.vo;

import lombok.Data;

/**
 * 商品评分统计 VO（仅统计审核通过的评价 status=1）。
 */
@Data
public class CommentStatsVO {
    /** 平均星（保留一位小数，由后端算好） */
    private Double avgStar;
    /** 总评价数 */
    private Long total;
    private Long fiveStar;
    private Long fourStar;
    private Long threeStar;
    private Long twoStar;
    private Long oneStar;
}
