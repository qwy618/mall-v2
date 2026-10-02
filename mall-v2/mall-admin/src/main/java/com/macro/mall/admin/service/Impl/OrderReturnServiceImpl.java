package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.admin.component.AdminUserDetails;
import com.macro.mall.admin.service.OrderReturnService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.OrderMapper;
import com.macro.mall.mbg.mapper.OrderOperateHistoryMapper;
import com.macro.mall.mbg.mapper.OrderReturnApplyMapper;
import com.macro.mall.mbg.model.OrderOperateHistory;
import com.macro.mall.mbg.model.OrderReturnApply;
import com.macro.mall.service.MemberPointsService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
public class OrderReturnServiceImpl implements OrderReturnService {

    @Autowired private OrderReturnApplyMapper returnApplyMapper;
    @Autowired private OrderOperateHistoryMapper historyMapper;
    @Autowired private OrderMapper orderMapper;
    @Autowired private MemberPointsService memberPointsService;

    @Override
    public CommonResult<CommonPage<OrderReturnApply>> list(Integer status, Integer pageNum, Integer pageSize) {
        IPage<OrderReturnApply> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<OrderReturnApply> w = new LambdaQueryWrapper<>();
        if (status != null) w.eq(OrderReturnApply::getStatus, status);
        w.orderByDesc(OrderReturnApply::getCreateTime);
        return CommonResult.success(CommonPage.restPage(returnApplyMapper.selectPage(page, w)));
    }

    @Override
    public CommonResult<OrderReturnApply> detail(Long id) {
        OrderReturnApply a = returnApplyMapper.selectById(id);
        if (a == null) return CommonResult.failed("申请不存在");
        return CommonResult.success(a);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> approve(Long id, String handleNote, String companyAddress) {
        OrderReturnApply a = returnApplyMapper.selectById(id);
        if (a == null) return CommonResult.failed("申请不存在");
        if (a.getStatus() != 0) return CommonResult.failed("仅待审核可申请");
        a.setStatus(1);
        a.setHandleNote(handleNote == null ? "" : handleNote);
        a.setCompanyAddress(companyAddress == null ? "" : companyAddress);
        a.setHandleMan(currentAdmin());
        a.setUpdateTime(LocalDateTime.now());
        returnApplyMapper.updateById(a);
        recordHistory(a, "RETURN_APPROVE", "同意退货，退货地址：" + companyAddress);
        return CommonResult.success(id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> reject(Long id, String handleNote) {
        OrderReturnApply a = returnApplyMapper.selectById(id);
        if (a == null) return CommonResult.failed("申请不存在");
        if (a.getStatus() != 0) return CommonResult.failed("仅待审核可拒绝");
        a.setStatus(2);
        a.setHandleNote(handleNote == null ? "" : handleNote);
        a.setHandleMan(currentAdmin());
        a.setUpdateTime(LocalDateTime.now());
        returnApplyMapper.updateById(a);
        recordHistory(a, "RETURN_REJECT", "拒绝退货：" + handleNote);
        return CommonResult.success(id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> receive(Long id) {
        OrderReturnApply a = returnApplyMapper.selectById(id);
        if (a == null) return CommonResult.failed("申请不存在");
        if (a.getStatus() != 1) return CommonResult.failed("仅已同意可确认收货");
        a.setStatus(3);
        a.setHandleMan(currentAdmin());
        a.setUpdateTime(LocalDateTime.now());
        returnApplyMapper.updateById(a);
        recordHistory(a, "RETURN_RECEIVE", "已收到退货商品");
        return CommonResult.success(id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> complete(Long id, String handleNote) {
        OrderReturnApply a = returnApplyMapper.selectById(id);
        if (a == null) return CommonResult.failed("申请不存在");
        if (a.getStatus() != 3) return CommonResult.failed("仅已收货可完成退款");
        a.setStatus(4);
        if (handleNote != null) a.setHandleNote(handleNote);
        a.setHandleMan(currentAdmin());
        a.setUpdateTime(LocalDateTime.now());
        returnApplyMapper.updateById(a);
        // 退款完成后回冲该笔退货对应的赠送积分（按退货金额 × 当前等级倍率，与赠送同口径）。
        // 不做的话"整单退货仍白拿积分"就是刷分漏洞。幂等由上方 status==3 守卫保证。
        int revoked = memberPointsService.revokeForReturn(a.getMemberId(), a.getOrderId(),
                a.getOrderSn(), a.getReturnAmount());
        recordHistory(a, "RETURN_COMPLETE", "退款完成，金额￥" + a.getReturnAmount()
                + (revoked > 0 ? ("，回冲积分 " + revoked) : ""));
        return CommonResult.success(id);
    }

    private void recordHistory(OrderReturnApply a, String type, String note) {
        OrderOperateHistory h = new OrderOperateHistory();
        h.setOrderId(a.getOrderId());
        h.setOrderSn(a.getOrderSn());
        h.setOperateMan(a.getHandleMan());
        h.setOperateType(type);
        h.setOperateNote(note);
        historyMapper.insert(h);
    }

    private String currentAdmin() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof AdminUserDetails d) {
            return d.getUsername();
        }
        return "admin";
    }
}
