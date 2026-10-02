package com.macro.mall.portal.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.OrderItemMapper;
import com.macro.mall.mbg.mapper.OrderMapper;
import com.macro.mall.mbg.mapper.OrderOperateHistoryMapper;
import com.macro.mall.mbg.mapper.OrderReturnApplyMapper;
import com.macro.mall.mbg.model.Order;
import com.macro.mall.mbg.model.OrderItem;
import com.macro.mall.mbg.model.OrderOperateHistory;
import com.macro.mall.mbg.model.OrderReturnApply;
import com.macro.mall.portal.dao.ApplyItem;
import com.macro.mall.portal.dao.ReturnApplyParam;
import com.macro.mall.portal.dao.ReturnItemDTO;
import com.macro.mall.portal.service.ReturnApplyService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@Slf4j
public class ReturnApplyServiceImpl implements ReturnApplyService {

    @Autowired private OrderMapper orderMapper;
    @Autowired private OrderItemMapper orderItemMapper;
    @Autowired private OrderReturnApplyMapper returnApplyMapper;
    @Autowired private OrderOperateHistoryMapper historyMapper;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> apply(Long memberId, ReturnApplyParam param) {
        if (param.getOrderId() == null || param.getItems() == null || param.getItems().isEmpty()) {
            return CommonResult.failed("参数不完整");
        }
        Order o = orderMapper.selectById(param.getOrderId());
        if (o == null) return CommonResult.failed("订单不存在");
        if (!memberId.equals(o.getMemberId())) return CommonResult.failed("无权操作");
        if (o.getStatus() != 3) return CommonResult.failed("仅已完成订单可申请退货");

        // 订单项快照（用于按 real_amount 算退款）
        List<OrderItem> items = orderItemMapper.selectList(
                new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, param.getOrderId()));
        Map<Long, OrderItem> itemMap = items.stream()
                .collect(Collectors.toMap(OrderItem::getId, i -> i));

        BigDecimal totalRefund = BigDecimal.ZERO;
        List<ReturnItemDTO> returnItems = new ArrayList<>();
        for (ApplyItem ai : param.getItems()) {
            OrderItem oi = itemMap.get(ai.getOrderItemId());
            if (oi == null) throw new BusinessException("退货项不存在");
            int qty = ai.getQuantity() == null ? 0 : ai.getQuantity();
            if (qty <= 0 || qty > oi.getQuantity()) throw new BusinessException("退货数量非法");
            // 退款 = 该行 real_amount × 退数/行数（债务7：按实付分摊退，杜绝按原价退）
            BigDecimal refund = oi.getRealAmount()
                    .multiply(BigDecimal.valueOf(qty))
                    .divide(BigDecimal.valueOf(oi.getQuantity()), 2, RoundingMode.HALF_UP);
            totalRefund = totalRefund.add(refund);
            returnItems.add(new ReturnItemDTO(oi.getId(), oi.getSkuId(), oi.getProductId(),
                    oi.getProductName(), oi.getProductPic(), qty, refund));
        }
        // 守卫：多行累加封顶到实付，防超退
        if (totalRefund.compareTo(o.getPayAmount()) > 0) {
            totalRefund = o.getPayAmount();
        }

        OrderReturnApply apply = new OrderReturnApply();
        apply.setOrderId(o.getId());
        apply.setOrderSn(o.getOrderSn());
        apply.setMemberId(memberId);
        apply.setReturnAmount(totalRefund.setScale(2, RoundingMode.HALF_UP));
        apply.setReason(param.getReason() == null ? "" : param.getReason());
        apply.setDescription(param.getDescription() == null ? "" : param.getDescription());
        try {
            apply.setProofPics(objectMapper.writeValueAsString(
                    param.getProofPics() == null ? new ArrayList<String>() : param.getProofPics()));
            apply.setReturnItems(objectMapper.writeValueAsString(returnItems));
        } catch (Exception e) {
            throw new BusinessException("凭证序列化失败");
        }
        apply.setStatus(0);
        returnApplyMapper.insert(apply);

        recordHistory(o.getId(), o.getOrderSn(), "会员" + memberId, "RETURN_APPLY",
                "申请退款￥" + apply.getReturnAmount());
        return CommonResult.success(apply.getId());
    }

    @Override
    public CommonResult<List<OrderReturnApply>> list(Long memberId) {
        List<OrderReturnApply> list = returnApplyMapper.selectList(
                new LambdaQueryWrapper<OrderReturnApply>()
                        .eq(OrderReturnApply::getMemberId, memberId)
                        .orderByDesc(OrderReturnApply::getCreateTime));
        return CommonResult.success(list);
    }

    @Override
    public CommonResult<OrderReturnApply> detail(Long memberId, Long id) {
        OrderReturnApply a = returnApplyMapper.selectById(id);
        if (a == null) return CommonResult.failed("申请不存在");
        if (!memberId.equals(a.getMemberId())) return CommonResult.failed("无权查看");
        return CommonResult.success(a);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> shipBack(Long memberId, Long id, String returnTrackingNo) {
        OrderReturnApply a = returnApplyMapper.selectById(id);
        if (a == null) return CommonResult.failed("申请不存在");
        if (!memberId.equals(a.getMemberId())) return CommonResult.failed("无权操作");
        if (a.getStatus() != 1) return CommonResult.failed("仅已同意的退货可回填物流");
        a.setReturnTrackingNo(returnTrackingNo);
        returnApplyMapper.updateById(a);
        recordHistory(a.getOrderId(), a.getOrderSn(), "会员" + memberId, "RETURN_SHIP_BACK",
                "会员回填退货物流：" + returnTrackingNo);
        return CommonResult.success(id);
    }

    private void recordHistory(Long orderId, String orderSn, String man, String type, String note) {
        OrderOperateHistory h = new OrderOperateHistory();
        h.setOrderId(orderId);
        h.setOrderSn(orderSn);
        h.setOperateMan(man);
        h.setOperateType(type);
        h.setOperateNote(note == null ? "" : note);
        historyMapper.insert(h);
    }
}
