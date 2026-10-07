package com.macro.mall.service.impl;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.macro.mall.mbg.mapper.SkuMapper;
import com.macro.mall.mbg.model.Sku;
import com.macro.mall.service.SkuStockService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/**
 * {@link SkuStockService} 实现。
 *
 * <p>全部动作用 MyBatis-Plus 的 LambdaUpdateWrapper 拼「条件 UPDATE」，
 * 与项目既有的库存写法一致（{@code setSql} 拼接 + {@code apply} 条件）。
 * 所有 quantity 都先经 {@link #requirePositive} 断言为正整数 —— 拼接进 SQL 的
 * 是 {@code int}，不存在注入面。
 */
@Slf4j
@Service
public class SkuStockServiceImpl implements SkuStockService {

    @Autowired
    private SkuMapper skuMapper;

    @Override
    public boolean lock(Long skuId, int quantity) {
        requirePositive(skuId, quantity);
        // UPDATE sku SET lock_stock = lock_stock + n
        //  WHERE id = ? AND stock - lock_stock >= n
        // 注意：条件必须是「可售」而不是 stock >= n —— 只看 stock 会把已被别人
        // 待支付订单占住的量算成可卖，直接超卖。
        int affected = skuMapper.update(null, new LambdaUpdateWrapper<Sku>()
                .eq(Sku::getId, skuId)
                .apply("stock - lock_stock >= {0}", quantity)
                .setSql("lock_stock = lock_stock + " + quantity));
        if (affected == 0) {
            // 正常业务分支（并发抢购时必然发生），不是异常
            log.info("锁定库存失败：可售不足 skuId={} quantity={}", skuId, quantity);
        }
        return affected > 0;
    }

    @Override
    public boolean consume(Long skuId, int quantity) {
        requirePositive(skuId, quantity);
        // UPDATE sku SET stock = stock - n, lock_stock = lock_stock - n
        //  WHERE id = ? AND lock_stock >= n
        // 条件只用 lock_stock >= n（「本单确实锁了这么多」这一语义前提）。
        // 不再叠 stock >= n：若全局不变量 lock <= stock 被脏数据破坏，应当由巡检断言
        // 暴露出来，而不是让一次正常支付因为无关的脏数据而失败。
        int affected = skuMapper.update(null, new LambdaUpdateWrapper<Sku>()
                .eq(Sku::getId, skuId)
                .apply("lock_stock >= {0}", quantity)
                .setSql("stock = stock - " + quantity + ", lock_stock = lock_stock - " + quantity));
        if (affected == 0) {
            // 说明该 SKU 没有对应的锁定记录 —— 属于数据/流程不一致，要大声报
            log.warn("扣减库存失败：无对应锁定记录，可能是不一致数据 skuId={} quantity={}", skuId, quantity);
        }
        return affected > 0;
    }

    @Override
    public boolean release(Long skuId, int quantity) {
        requirePositive(skuId, quantity);
        // UPDATE sku SET lock_stock = lock_stock - n
        //  WHERE id = ? AND lock_stock >= n
        // 注意：lock_stock >= n 是天然幂等守卫 —— 重复释放第二次 affected = 0，
        // 不会把 lock_stock 减成负数。但它**挡不住**「一次取消归还两次」——
        // 独占性由调用方的原子状态流转（status 0→4）保证，见接口 javadoc。
        int affected = skuMapper.update(null, new LambdaUpdateWrapper<Sku>()
                .eq(Sku::getId, skuId)
                .apply("lock_stock >= {0}", quantity)
                .setSql("lock_stock = lock_stock - " + quantity));
        if (affected == 0) {
            log.warn("释放库存失败：无锁定可释放（重复释放或数据不一致）skuId={} quantity={}", skuId, quantity);
        }
        return affected > 0;
    }

    @Override
    public void restore(Long skuId, int quantity) {
        requirePositive(skuId, quantity);
        // UPDATE sku SET stock = stock + n WHERE id = ?
        skuMapper.update(null, new LambdaUpdateWrapper<Sku>()
                .eq(Sku::getId, skuId)
                .setSql("stock = stock + " + quantity));
    }

    @Override
    public int available(Sku sku) {
        if (sku == null) return 0;
        int stock = sku.getStock() == null ? 0 : sku.getStock();
        int lock = sku.getLockStock() == null ? 0 : sku.getLockStock();
        return Math.max(0, stock - lock);
    }

    private void requirePositive(Long skuId, int quantity) {
        if (skuId == null) throw new IllegalArgumentException("skuId 不能为空");
        if (quantity <= 0) throw new IllegalArgumentException("quantity 必须为正整数，实际=" + quantity);
    }
}
