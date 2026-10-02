package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.admin.dto.CouponParam;
import com.macro.mall.admin.service.CouponService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.mapper.CouponMapper;
import com.macro.mall.mbg.model.Coupon;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class CouponServiceImpl implements CouponService {
    @Autowired
    private CouponMapper couponMapper;
    @Override
    public CommonResult<CommonPage<Coupon>> listCoupons(Integer pageNum, Integer pageSize, Integer useType, String keyword) {
        IPage<Coupon> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<Coupon> w = new LambdaQueryWrapper<>();
        if (useType != null) {
            w.eq(Coupon::getUseType, useType);
        }
        if (StringUtils.hasText(keyword)) {
            w.like(Coupon::getName, keyword);   // 单 like，无 OR，无需 and() 包裹
        }
        w.orderByDesc(Coupon::getCreateTime);    // 可选：按创建时间倒序
        couponMapper.selectPage(page, w);
        return CommonResult.success(CommonPage.restPage(page));
    }

    @Override
    public CommonResult<Coupon> detail(Long id) {
        Coupon coupon = couponMapper.selectById(id);
        if (coupon == null) {
            return CommonResult.failed("优惠券不存在");
        }
        return CommonResult.success(coupon);
    }

    @Override
    public CommonResult<Long> createCoupon(CouponParam param) {
        Coupon coupon = new Coupon();
        BeanUtils.copyProperties(param, coupon);   // Spring 版：参数顺序 (source, target)
        couponMapper.insert(coupon);               // MP 跳过 null 列，min_point/create_time/delete_status 全走 DB 默认
        return CommonResult.success(coupon.getId());
    }

    @Override
    public CommonResult<Integer> updateCoupon(Long id, CouponParam param) {
        Coupon existing = couponMapper.selectById(id);
        if (existing == null) {
            return CommonResult.failed("优惠券不存在");
        }
        Coupon coupon = new Coupon();
        coupon.setId(id);                              // 必须设主键，updateById 才能定位
        BeanUtils.copyProperties(param, coupon);       // 同名属性拷过去
        // createTime / deleteStatus / receiveCount / useCount 不 set（保持原值，不覆盖）
        int rows = couponMapper.updateById(coupon);
        return CommonResult.success(rows);
    }

    @Override
    public CommonResult<Integer> deleteCoupon(Long id) {
        int rows = couponMapper.deleteById(id);   // 全局逻辑删：自动 SET delete_status=1
        return CommonResult.success(rows);
    }
}
