package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.admin.service.CouponHistoryService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.mapper.CouponHistoryMapper;
import com.macro.mall.mbg.mapper.CouponMapper;
import com.macro.mall.mbg.model.Coupon;
import com.macro.mall.mbg.model.CouponHistory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class CouponHistoryServiceImpl implements CouponHistoryService {
    @Autowired
    private CouponMapper couponMapper;
    @Autowired
    private CouponHistoryMapper couponHistoryMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> receive(Long couponId, Long memberId) {
        // 1) 券是否存在
        Coupon coupon = couponMapper.selectById(couponId);
        if (coupon == null) {
            return CommonResult.failed("优惠券不存在");
        }
        // 2) 余量校验
        if (coupon.getReceiveCount() >= coupon.getPublishCount()) {
            return CommonResult.failed("优惠券已领取完");
        }
        // 3) 每人限领校验
        LambdaQueryWrapper<CouponHistory> w = new LambdaQueryWrapper<>();
        w.eq(CouponHistory::getCouponId, couponId)
                .eq(CouponHistory::getMemberId, memberId);
        long owned = couponHistoryMapper.selectCount(w);
        if (owned >= coupon.getPerLimit()) {
            return CommonResult.failed("超过每人限领数量");
        }
        // 4) 插领取记录
        CouponHistory history = new CouponHistory();
        history.setCouponId(couponId);
        history.setMemberId(memberId);
        history.setStatus(0);          // 未使用
        // createTime 不 set，交 DB 默认；useTime 为 null
        couponHistoryMapper.insert(history);
        // 5) 券已领取数 +1
        coupon.setReceiveCount(coupon.getReceiveCount() + 1);
        couponMapper.updateById(coupon);
        return CommonResult.success(history.getId());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Void> use(Long historyId, Long orderId, String orderSn) {
        // 1) 领取记录是否存在
        CouponHistory history = couponHistoryMapper.selectById(historyId);
        if (history == null) {
            return CommonResult.failed("领取记录不存在");
        }
        // 2) 状态校验：只有未使用(0)能核销
        if (history.getStatus() != 0) {
            return CommonResult.failed("该优惠券已使用或已过期");
        }
        // 3) 核销：status 0→1 + 写订单关联 + 使用时间
        history.setStatus(1);
        history.setOrderId(orderId);
        history.setOrderSn(orderSn);
        history.setUseTime(LocalDateTime.now());
        couponHistoryMapper.updateById(history);
        // 4) 券已使用数 +1（同事务，防超扣）
        Coupon coupon = couponMapper.selectById(history.getCouponId());
        if (coupon != null) {
            Integer used = coupon.getUseCount() == null ? 0 : coupon.getUseCount();
            coupon.setUseCount(used + 1);
            couponMapper.updateById(coupon);
        }
        return CommonResult.success(null);
    }

    @Override
    public CommonResult<List<CouponHistory>> listByMember(Long memberId, Integer status) {
        LambdaQueryWrapper<CouponHistory> w = new LambdaQueryWrapper<>();
        w.eq(CouponHistory::getMemberId, memberId);
        if (status != null) {
            w.eq(CouponHistory::getStatus, status);   // 可选筛选：0未用/1已用/2过期
        }
        return CommonResult.success(couponHistoryMapper.selectList(w));
    }

    @Override
    public CommonResult<CommonPage<CouponHistory>> listHistories(Long couponId, Integer pageNum, Integer pageSize) {
        Page<CouponHistory> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<CouponHistory> w = new LambdaQueryWrapper<>();
        w.eq(CouponHistory::getCouponId, couponId);
        couponHistoryMapper.selectPage(page, w);
        return CommonResult.success(CommonPage.restPage(page));
    }
}
