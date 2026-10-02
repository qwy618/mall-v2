package com.macro.mall.portal.service;

import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.portal.dao.CommentSubmitParam;
import com.macro.mall.portal.vo.CommentStatsVO;
import com.macro.mall.portal.vo.ProductCommentVO;

/**
 * 商品评价服务（C 端）。
 */
public interface CommentService {

    /** 提交评价（含越权 / 订单状态 / 重复评价校验） */
    CommonResult<Void> submit(Long memberId, CommentSubmitParam param);

    /** 商品评价列表（公开，仅审核通过 status=1） */
    CommonResult<CommonPage<ProductCommentVO>> listProductComments(Long productId, int pageNum, int pageSize);

    /** 商品评分统计（仅审核通过 status=1） */
    CommonResult<CommentStatsVO> getStats(Long productId);

    /** 我的评价（登录，含全部状态，便于「待审核/被驳回」提示） */
    CommonResult<CommonPage<ProductCommentVO>> listMine(Long memberId, int pageNum, int pageSize);
}
