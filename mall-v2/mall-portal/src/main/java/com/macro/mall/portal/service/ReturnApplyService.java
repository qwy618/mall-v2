package com.macro.mall.portal.service;

import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.OrderReturnApply;
import com.macro.mall.portal.dao.ReturnApplyParam;

import java.util.List;

public interface ReturnApplyService {

    /** 申请退货：退款金额 = Σ(real_amount × 退数/行数)，守卫 ≤ 实付 */
    CommonResult<Long> apply(Long memberId, ReturnApplyParam param);

    /** 我的退货申请列表 */
    CommonResult<List<OrderReturnApply>> list(Long memberId);

    /** 申请详情（越权校验） */
    CommonResult<OrderReturnApply> detail(Long memberId, Long id);

    /** 会员回填退货物流单号 */
    CommonResult<Long> shipBack(Long memberId, Long id, String returnTrackingNo);
}
