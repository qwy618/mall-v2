package com.macro.mall.service;

import com.macro.mall.common.CommonPage;
import com.macro.mall.mbg.model.MemberIntegrationHistory;

import java.math.BigDecimal;

/**
 * 会员积分与成长值（债务18 / 订单域收尾）：下单抵扣、交易完成赠送、退货回冲、无效单退回、流水查询。
 *
 * <p>换算规则：{@link #POINTS_PER_YUAN} 积分 = 1 元。
 * 赠送规则：积分 = floor(实付 × 等级积分倍率%)，成长值 = 实付金额（1 元 = 1 成长值）。
 *
 * <p>放在 mall-service 共享模块：C 端下单/确认收货与后台代确认收货、退货完成都走同一套逻辑，
 * 避免"后台操作不发积分 / 退货不回冲积分"这类两个应用各写一份导致的口径漂移。
 */
public interface MemberPointsService {

    /** 100 积分 = 1 元 */
    int POINTS_PER_YUAN = 100;

    int TYPE_GRANT = 1;         // 下单赠送（交易完成）
    int TYPE_CONSUME = 2;       // 下单抵扣
    int TYPE_RETURN_BACK = 3;   // 退货扣回
    int TYPE_ADMIN = 4;         // 管理员调整
    int TYPE_INVALID_BACK = 5;  // 无效单作废，退回已抵扣积分

    /**
     * 下单抵扣：原子条件扣减（余额充足才扣，防并发超用）+ 记流水。
     * 余额不足抛 BusinessException。
     */
    void consumeForOrder(Long memberId, Long orderId, String orderSn, int points);

    /**
     * 交易完成（确认收货）赠送：加积分 + 加成长值 + 按新成长值自动升级 + 记流水。
     * 幂等由调用方（确认收货的原子状态流转）保证，每单只调用一次。
     */
    void grantForOrder(Long memberId, Long orderId, String orderSn, BigDecimal payAmount);

    /**
     * 退货完成后回冲赠送积分：按退货金额与当前等级倍率重算
     * （回冲 = floor(退货金额 × 倍率%)，与赠送同口径）。
     * 原子条件扣减：余额不足则扣到 0，绝不扣成负数；记 {@link #TYPE_RETURN_BACK} 流水。
     *
     * @return 实际回冲的积分数
     */
    int revokeForReturn(Long memberId, Long orderId, String orderSn, BigDecimal returnAmount);

    /**
     * 无效单作废：退回下单时已抵扣的积分（全额退回），记 {@link #TYPE_INVALID_BACK} 流水。
     */
    void refundConsumed(Long memberId, Long orderId, String orderSn, int points);

    /** 积分流水（倒序分页） */
    CommonPage<MemberIntegrationHistory> listHistory(Long memberId, Integer pageNum, Integer pageSize);
}
