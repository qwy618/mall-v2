package com.macro.mall.admin.service;

import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.OrderReturnApply;

public interface OrderReturnService {

    /** 售后申请列表（按状态筛） */
    CommonResult<CommonPage<OrderReturnApply>> list(Integer status, Integer pageNum, Integer pageSize);

    /** 详情 */
    CommonResult<OrderReturnApply> detail(Long id);

    /** 同意退货（填退货地址） */
    CommonResult<Long> approve(Long id, String handleNote, String companyAddress);

    /** 拒绝 */
    CommonResult<Long> reject(Long id, String handleNote);

    /** 确认收到退货商品 */
    CommonResult<Long> receive(Long id);

    /** 完成退款（标记退款完成；真实打款暂缓，支付为 Mock） */
    CommonResult<Long> complete(Long id, String handleNote);
}
