package com.macro.mall.service;

import com.macro.mall.mbg.model.Sku;

/**
 * SKU 库存口径 —— **portal 与 admin 共用的唯一实现**（债务 5：库存锁定释放）。
 *
 * <h3>两个计数器</h3>
 * <ul>
 *   <li>{@code stock} —— 实物库存（真正在库里的数量）</li>
 *   <li>{@code lock_stock} —— 锁定库存（已被「待支付订单」预占的数量）</li>
 *   <li><b>可售库存 = stock − lock_stock</b>：任何「还有没有货」的判断都必须用这个，
 *       光看 {@code stock} 会以为有货，其实早被别人的待支付订单占住了。</li>
 * </ul>
 *
 * <h3>订单状态流转 ↔ 库存动作（一一对应）</h3>
 * <pre>
 *   下单（新建 status=0）      → lock()       lock_stock += n
 *   支付（0 → 1）             → consume()    stock -= n, lock_stock -= n
 *   取消 / 超时关单（0 → 4）   → release()    lock_stock -= n
 *   作废订单（1 → 5）         → restore()    stock += n   （货没出库，退回实物库存）
 *   发货 / 完成 / 收货         → 不动作
 * </pre>
 *
 * <h3>为什么必须这样写（并发要点）</h3>
 * <ol>
 *   <li>三个动作**全部**是「条件 UPDATE + 检查 affected rows」，绝不「先查再改」——
 *       查与改之间的窗口就是超卖/超发的来源。判断与写入必须落在同一条 SQL 里，
 *       由 InnoDB 行锁保证原子。</li>
 *   <li>锁库条件用 {@code stock - lock_stock >= n}（可售够）而不是 {@code stock >= n}。</li>
 *   <li>释放条件带 {@code lock_stock >= n}，这是**天然幂等守卫**：重复释放第二次
 *       affected = 0，不会把 {@code lock_stock} 减成负数。</li>
 * </ol>
 *
 * <p><b>⚠️ 但光有 SQL 条件还不够</b>：{@link #release} 只能保证「不减成负数」，
 * 挡不住「一次取消归还两次」。因此调用方必须保证**释放由「订单状态流转成功」的那个
 * 线程独占执行** —— 即先用原子条件更新把状态从 0 改到 4（affected == 0 就直接返回），
 * 成功者才调用 release。参见 {@code OrderServiceImpl.cancel} /
 * {@code cancelExpiredBySystem}。
 *
 * <p>本类不做事务控制，所有方法都运行在调用方的事务里。
 */
public interface SkuStockService {

    /**
     * 下单预占：{@code lock_stock += n}，仅当**可售**（stock − lock_stock）足够。
     *
     * @return true = 占用成功；false = 可售不足（调用方应据此判定「库存不足」并回滚整单）
     */
    boolean lock(Long skuId, int quantity);

    /**
     * 支付扣减（真出库）：{@code stock -= n, lock_stock -= n}，仅当已锁数量足够。
     *
     * <p>之所以两步一起做：下单时已经把 n 从「可售」挪进「锁定」，支付时这笔预占
     * 转为真实消耗 —— 可售数量在支付前后**不变**（下单时已经减过了），这是正确行为。
     *
     * @return true = 扣减成功；false = 没有对应的锁定记录（数据不一致，见实现里的告警）
     */
    boolean consume(Long skuId, int quantity);

    /**
     * 释放预占（取消 / 超时关单）：{@code lock_stock -= n}。
     *
     * <p>带 {@code lock_stock >= n} 条件，因此天然幂等。调用方必须确保同一笔订单
     * 只有「状态流转成功」的那一个线程会调用本方法。
     *
     * @return true = 释放成功；false = 没有可释放的锁定（重复释放或数据不一致）
     */
    boolean release(Long skuId, int quantity);

    /**
     * 实物库存回滚（作废已支付订单，1 → 5）：{@code stock += n}。
     *
     * <p>作废的对象是**已支付**订单，此时 {@link #consume} 已经把实物库存扣掉了，
     * 而货并没有真的发出去，所以要加回 {@code stock}（不是动 {@code lock_stock}）。
     */
    void restore(Long skuId, int quantity);

    /**
     * 可售库存 = {@code stock − lock_stock}，下限 0。
     *
     * <p>做下限保护是因为显示层不应出现负数（历史脏数据可能造成 lock &gt; stock）；
     * 数据是否真的坏掉靠巡检断言（lock ≥ 0 且 lock ≤ stock）来发现。
     */
    int available(Sku sku);
}
