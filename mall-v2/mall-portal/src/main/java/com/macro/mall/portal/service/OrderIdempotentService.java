package com.macro.mall.portal.service;

/**
 * 下单幂等令牌（债务23）。
 *
 * <p>基于 Redis 一次性 Token：进入确认订单页时 {@link #generate} 取号，提交订单时 {@link #claim} 原子认领，
 * 成功 {@link #finish} 回填订单号，失败 {@link #release} 回退允许重试。
 *
 * <p>存储：{@code idem:order:{memberId}:{token}}，TTL 900s，值状态机：
 * <ul>
 *   <li>{@code "0"}     未使用（刚取号）</li>
 *   <li>{@code "P"}     处理中（已被某请求独占）</li>
 *   <li>{@code orderId} 已完成（重复请求返回该单号，实现幂等返回同结果）</li>
 * </ul>
 */
public interface OrderIdempotentService {

    /** 生成一次性令牌并写 Redis（状态=0，TTL 900s），返回给前端。 */
    String generate(Long memberId);

    /**
     * 原子认领令牌。
     *
     * @return {@code -1} 令牌无效/已过期；{@code -2} 已有同名请求处理中；
     *         {@code 0} 认领成功（可下单）；{@code >0} 已完成，返回已生成的 orderId
     */
    Long claim(Long memberId, String token);

    /** 下单成功后回填订单号，使后续同 token 请求返回同一笔单。 */
    void finish(Long memberId, String token, Long orderId);

    /** 下单失败回退：仅当状态为 {@code P} 时置回 {@code 0}，绝不覆盖已完成状态。 */
    void release(Long memberId, String token);
}
