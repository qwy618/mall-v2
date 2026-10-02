package com.macro.mall.portal.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.CouponHistoryMapper;
import com.macro.mall.mbg.mapper.CouponMapper;
import com.macro.mall.mbg.mapper.ProductMapper;
import com.macro.mall.mbg.mapper.SkuMapper;
import com.macro.mall.mbg.model.Coupon;
import com.macro.mall.mbg.model.CouponHistory;
import com.macro.mall.mbg.model.Product;
import com.macro.mall.mbg.model.Sku;
import com.macro.mall.portal.dao.CouponEstimateParam;
import com.macro.mall.portal.service.CouponService;
import com.macro.mall.portal.vo.CouponEstimateVO;
import com.macro.mall.portal.vo.MyCouponVO;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

@Service
public class CouponServiceImpl implements CouponService {

    private final CouponMapper couponMapper;
    private final CouponHistoryMapper couponHistoryMapper;
    private final RedissonClient redisson;
    private final SkuMapper skuMapper;
    private final ProductMapper productMapper;

    public CouponServiceImpl(CouponMapper couponMapper, CouponHistoryMapper couponHistoryMapper,
                             RedissonClient redisson, SkuMapper skuMapper, ProductMapper productMapper) {
        this.couponMapper = couponMapper;
        this.couponHistoryMapper = couponHistoryMapper;
        this.redisson = redisson;
        this.skuMapper = skuMapper;
        this.productMapper = productMapper;
    }

    @Override
    public List<Coupon> listAvailable() {
        LambdaQueryWrapper<Coupon> w = new LambdaQueryWrapper<>();
        // 未删除，且（无结束时间 或 结束时间未到）
        w.eq(Coupon::getDeleteStatus, 0)
                .and(aw -> aw.isNull(Coupon::getEndTime)
                        .or().gt(Coupon::getEndTime, LocalDateTime.now()))
                .orderByDesc(Coupon::getId);
        return couponMapper.selectList(w);
    }

    /**
     * 领取优惠券 —— 并发安全的核心。
     *
     * 与 admin 端“先 select 再 +1”不同，这里把“判断余量 + 自增”合并成一条
     * 带条件的原子 UPDATE，由数据库在行上加锁串行执行，从根本上杜绝超发：
     *
     *   UPDATE coupon
     *      SET receive_count = receive_count + 1
     *    WHERE id = ? AND delete_status = 0
     *      AND publish_count IS NOT NULL
     *      AND receive_count < publish_count
     *
     * affected rows = 0 说明已被抢光（或不存在），直接返回失败，无需回滚。
     * 随后插入领取记录；coupon_history(coupon_id, member_id) 上的唯一索引
     * 会把“同一会员重复领取”在数据库层拦下，捕获 DuplicateKeyException 后
     * 抛出 RuntimeException 触发整个事务回滚（含上面的自增）。
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Void> receive(Long memberId, Long couponId) {
        if (memberId == null || couponId == null) {
            return CommonResult.validateFailed("参数不能为空");
        }
        RLock lock = redisson.getLock("coupon:receive:" + couponId);
        boolean locked = false;
        try {
            locked = lock.tryLock(3, 10, TimeUnit.SECONDS);
            if (!locked) {
                return CommonResult.failed("当前领取人数过多，请稍后再试");
            }
            Coupon coupon = couponMapper.selectById(couponId);
            if (coupon == null || coupon.getDeleteStatus() == 1) {
                return CommonResult.failed("优惠券不存在或已删除");
            }
            LocalDateTime now = LocalDateTime.now();
            if ((coupon.getStartTime() != null && coupon.getStartTime().isAfter(now))
                    || (coupon.getEndTime() != null && coupon.getEndTime().isBefore(now))) {
                return CommonResult.failed("优惠券已过期或未开始，请注意时间");
            }
            LambdaQueryWrapper<CouponHistory> w = new LambdaQueryWrapper<>();
            w.eq(CouponHistory::getMemberId, memberId)
                    .eq(CouponHistory::getCouponId, couponId);
            if (couponHistoryMapper.selectCount(w) > 0) {
                return CommonResult.failed("您已领取过该优惠券");
            }
            LambdaUpdateWrapper<Coupon> u = new LambdaUpdateWrapper<>();
            u.eq(Coupon::getId, couponId)
                    .gt(Coupon::getPublishCount, coupon.getReceiveCount())
                    .setSql("receive_count = receive_count + 1");
            if (couponMapper.update(u) == 0) {
                return CommonResult.failed("优惠券已抢光");
            }
            CouponHistory history = new CouponHistory();
            history.setCouponId(couponId);
            history.setMemberId(memberId);
            history.setCouponCode(generateCouponCode(memberId, couponId));
            history.setStatus(0);
            history.setCreateTime(now);
            try {
                couponHistoryMapper.insert(history);
            } catch (DuplicateKeyException e) {
                throw new BusinessException("您已领取过该优惠券"); // 回滚 + 友好提示
            }
            return CommonResult.success();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();   // 恢复中断标志
            return CommonResult.failed("领取失败，请稍后再试");
        } finally {
            if (lock.isHeldByCurrentThread()) {    // ★ 关键：任何 return/异常都释放
                lock.unlock();
            }
        }
    }


    @Override
    public List<MyCouponVO> myCoupons(Long memberId) {
        LambdaQueryWrapper<CouponHistory> w = new LambdaQueryWrapper<>();
        w.eq(CouponHistory::getMemberId, memberId)
                .orderByDesc(CouponHistory::getCreateTime);
        List<CouponHistory> histories = couponHistoryMapper.selectList(w);

        List<MyCouponVO> result = new ArrayList<>(histories.size());
        for (CouponHistory h : histories) {
            Coupon coupon = couponMapper.selectById(h.getCouponId());
            MyCouponVO vo = new MyCouponVO();
            vo.setCoupon(coupon);
            vo.setStatus(h.getStatus());
            vo.setCreateTime(h.getCreateTime());
            result.add(vo);
        }
        return result;
    }

    /**
     * 预估可用券（确认订单页预览，只读不核销）。
     * 与 createOrder 共用同一套 useType / couponBase 规则，保证“页面显示可用/优惠X”
     * 与“下单实扣X”完全一致。
     */
    @Override
    public List<CouponEstimateVO> estimate(Long memberId, CouponEstimateParam param) {
        List<CouponEstimateParam.EstimateItem> items = param.getItems();
        if (items == null || items.isEmpty()) {
            return new ArrayList<>();
        }
        // 1. 批量查 sku → productId；批量查 product → categoryId
        Set<Long> skuIds = items.stream().map(CouponEstimateParam.EstimateItem::getSkuId)
                .filter(Objects::nonNull).collect(Collectors.toSet());
        List<Sku> skuList = skuIds.isEmpty() ? new ArrayList<>() : skuMapper.selectBatchIds(skuIds);
        Map<Long, Sku> skuMap = skuList.stream().collect(Collectors.toMap(Sku::getId, s -> s));
        Set<Long> productIds = skuList.stream().map(Sku::getProductId)
                .filter(Objects::nonNull).collect(Collectors.toSet());
        List<Product> productList = productIds.isEmpty() ? new ArrayList<>() : productMapper.selectBatchIds(productIds);
        Map<Long, Product> productMap = productList.stream()
                .collect(Collectors.toMap(Product::getId, p -> p));

        // 1.1 订单项 → 每行数量（同 sku 合并）
        Map<Long, Integer> qtyMap = items.stream()
                .filter(it -> it.getSkuId() != null)
                .collect(Collectors.toMap(
                        CouponEstimateParam.EstimateItem::getSkuId,
                        it -> it.getQuantity() == null ? 0 : it.getQuantity(),
                        Integer::sum));

        // 2. 查该会员未使用券
        LambdaQueryWrapper<CouponHistory> hw = new LambdaQueryWrapper<>();
        hw.eq(CouponHistory::getMemberId, memberId).eq(CouponHistory::getStatus, 0);
        List<CouponHistory> histories = couponHistoryMapper.selectList(hw);

        LocalDateTime now = LocalDateTime.now();
        List<CouponEstimateVO> result = new ArrayList<>(histories.size());
        for (CouponHistory h : histories) {
            Coupon coupon = couponMapper.selectById(h.getCouponId());
            if (coupon == null || coupon.getDeleteStatus() == 1) {
                continue; // 券已删除，跳过
            }
            CouponEstimateVO vo = new CouponEstimateVO();
            vo.setCoupon(coupon);

            // 3. 按 useType 累加适用商品小计（券适用商品小计 couponBase）
            BigDecimal baseAmount = BigDecimal.ZERO;
            for (Map.Entry<Long, Integer> e : qtyMap.entrySet()) {
                Sku sku = skuMap.get(e.getKey());
                if (sku == null || e.getValue() <= 0) continue;
                Product product = productMap.get(sku.getProductId());
                boolean applies = false;
                Integer useType = coupon.getUseType();
                if (useType == null || useType == 0) {                 // 全场通用
                    applies = true;
                } else if (useType == 1) {                             // 指定分类
                    applies = product != null
                            && Objects.equals(coupon.getCategoryId(), product.getCategoryId());
                } else if (useType == 2) {                             // 指定商品
                    applies = product != null
                            && Objects.equals(coupon.getProductId(), product.getId());
                }
                if (applies) {
                    baseAmount = baseAmount.add(
                            sku.getPrice().multiply(BigDecimal.valueOf(e.getValue())));
                }
            }
            vo.setBaseAmount(baseAmount);

            // 4. 时间 + 门槛 + 类型校验
            if (coupon.getStartTime() != null && now.isBefore(coupon.getStartTime())) {
                vo.setUsable(false);
                vo.setReason("优惠券未到使用时间");
                vo.setDiscount(BigDecimal.ZERO);
            } else if (coupon.getEndTime() != null && now.isAfter(coupon.getEndTime())) {
                vo.setUsable(false);
                vo.setReason("优惠券已过期");
                vo.setDiscount(BigDecimal.ZERO);
            } else if (coupon.getAmount() == null
                    || coupon.getAmount().compareTo(BigDecimal.ZERO) <= 0) {
                vo.setUsable(false);
                vo.setReason("优惠券类型不支持");
                vo.setDiscount(BigDecimal.ZERO);
            } else {
                BigDecimal min = coupon.getMinPoint() == null ? BigDecimal.ZERO : coupon.getMinPoint();
                if (baseAmount.compareTo(min) < 0) {
                    vo.setUsable(false);
                    vo.setReason("适用商品金额未达使用门槛");
                    vo.setDiscount(BigDecimal.ZERO);
                } else {
                    BigDecimal discount = coupon.getAmount().min(baseAmount)
                            .setScale(2, RoundingMode.HALF_UP);
                    vo.setUsable(true);
                    vo.setDiscount(discount);
                    vo.setReason(null);
                }
            }
            result.add(vo);
        }
        return result;
    }

    private String generateCouponCode(Long memberId, Long couponId) {
        return "C" + couponId + "M" + memberId + (System.nanoTime() % 100000);
    }
}
