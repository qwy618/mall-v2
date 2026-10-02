package com.macro.mall.admin.service;

import com.macro.mall.admin.vo.CommentListItemVO;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;

/**
 * 商品评价后台服务。
 */
public interface CommentService {

    /** 列表（分页；productId / status / keyword(昵称或商品名) 筛选） */
    CommonResult<CommonPage<CommentListItemVO>> list(Integer pageNum, Integer pageSize,
                                                    Long productId, Integer status, String keyword);

    /** 审核：status=1 通过 / status=2 驳回 */
    CommonResult<Void> audit(Long id, Integer status);

    /** 商家回复 */
    CommonResult<Void> reply(Long id, String replyContent);

    /** 删除（物理删） */
    CommonResult<Void> delete(Long id);
}
