package com.macro.mall.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.MemberIntegrationHistoryMapper;
import com.macro.mall.mbg.mapper.MemberMapper;
import com.macro.mall.mbg.model.Member;
import com.macro.mall.mbg.model.MemberIntegrationHistory;
import com.macro.mall.mbg.model.MemberLevel;
import com.macro.mall.service.MemberLevelService;
import com.macro.mall.service.MemberPointsService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;

@Service
@Slf4j
public class MemberPointsServiceImpl implements MemberPointsService {

    private final MemberMapper memberMapper;
    private final MemberIntegrationHistoryMapper historyMapper;
    private final MemberLevelService memberLevelService;

    public MemberPointsServiceImpl(MemberMapper memberMapper,
                                   MemberIntegrationHistoryMapper historyMapper,
                                   MemberLevelService memberLevelService) {
        this.memberMapper = memberMapper;
        this.historyMapper = historyMapper;
        this.memberLevelService = memberLevelService;
    }

    @Override
    public void consumeForOrder(Long memberId, Long orderId, String orderSn, int points) {
        if (points <= 0) return;
        // 原子条件扣减：余额充足才扣。并发下两个请求不会把积分扣成负数
        int rows = memberMapper.update(null, new LambdaUpdateWrapper<Member>()
                .eq(Member::getId, memberId)
                .ge(Member::getIntegration, points)
                .setSql("integration = integration - " + points));
        if (rows == 0) {
            throw new BusinessException("积分不足，请调整后重试");
        }
        Member latest = memberMapper.selectById(memberId);
        record(memberId, orderId, orderSn, TYPE_CONSUME, -points,
                latest == null ? 0 : latest.getIntegration(),
                "会员" + memberId, "下单抵扣积分（" + POINTS_PER_YUAN + "积分=1元）");
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void grantForOrder(Long memberId, Long orderId, String orderSn, BigDecimal payAmount) {
        if (payAmount == null || payAmount.compareTo(BigDecimal.ZERO) <= 0) return;
        Member member = memberMapper.selectById(memberId);
        if (member == null) return;

        MemberLevel level = memberLevelService.matchByGrowth(member.getGrowth());
        int rate = level == null || level.getIntegrationRate() == null ? 100 : level.getIntegrationRate();

        // 赠送积分 = 实付 × 倍率（向下取整）；成长值 = 实付金额（1 元 = 1 成长值）
        int points = payAmount.multiply(BigDecimal.valueOf(rate))
                .divide(BigDecimal.valueOf(100), 0, RoundingMode.DOWN).intValue();
        int growthAdd = payAmount.setScale(0, RoundingMode.DOWN).intValue();
        if (points <= 0 && growthAdd <= 0) return;

        // 原子累加（MySQL 行锁），避免并发订单互相覆盖
        memberMapper.update(null, new LambdaUpdateWrapper<Member>()
                .eq(Member::getId, memberId)
                .setSql("integration = integration + " + points
                        + ", history_integration = history_integration + " + points
                        + ", growth = growth + " + growthAdd));

        Member latest = memberMapper.selectById(memberId);
        if (latest == null) return;

        // 按新成长值重算等级（只升不降：成长值只增，匹配结果自然单调）
        MemberLevel matched = memberLevelService.matchByGrowth(latest.getGrowth());
        if (matched != null && !matched.getId().equals(latest.getLevelId())) {
            memberMapper.update(null, new LambdaUpdateWrapper<Member>()
                    .eq(Member::getId, memberId)
                    .set(Member::getLevelId, matched.getId()));
            log.info("会员 {} 升级：{} -> {}", memberId, latest.getLevelId(), matched.getId());
        }

        if (points > 0) {
            record(memberId, orderId, orderSn, TYPE_GRANT, points,
                    latest.getIntegration() == null ? points : latest.getIntegration(),
                    "system", "订单完成赠送积分（" + rate + "% 倍率）");
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public int revokeForReturn(Long memberId, Long orderId, String orderSn, BigDecimal returnAmount) {
        if (returnAmount == null || returnAmount.compareTo(BigDecimal.ZERO) <= 0) return 0;
        Member member = memberMapper.selectById(memberId);
        if (member == null) return 0;

        // 与赠送同口径：按当前等级倍率把"退货金额"折算成应回冲积分
        MemberLevel level = memberLevelService.matchByGrowth(member.getGrowth());
        int rate = level == null || level.getIntegrationRate() == null ? 100 : level.getIntegrationRate();
        int want = returnAmount.multiply(BigDecimal.valueOf(rate))
                .divide(BigDecimal.valueOf(100), 0, RoundingMode.DOWN).intValue();
        if (want <= 0) return 0;

        // 余额不足则扣到 0（不允许扣成负数）：条件更新保证并发安全
        int balance = member.getIntegration() == null ? 0 : member.getIntegration();
        int actual = Math.min(want, balance);
        if (actual <= 0) {
            log.info("会员 {} 退货回冲积分跳过（当前余额 0），应回冲 {}", memberId, want);
            return 0;
        }
        memberMapper.update(null, new LambdaUpdateWrapper<Member>()
                .eq(Member::getId, memberId)
                .ge(Member::getIntegration, actual)
                .setSql("integration = integration - " + actual));

        Member latest = memberMapper.selectById(memberId);
        record(memberId, orderId, orderSn, TYPE_RETURN_BACK, -actual,
                latest == null ? 0 : latest.getIntegration(),
                "system", "退货回冲积分（退货金额￥" + returnAmount.setScale(2, RoundingMode.HALF_UP) + "，应回冲 " + want + "）");
        return actual;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void refundConsumed(Long memberId, Long orderId, String orderSn, int points) {
        if (points <= 0) return;
        memberMapper.update(null, new LambdaUpdateWrapper<Member>()
                .eq(Member::getId, memberId)
                .setSql("integration = integration + " + points));
        Member latest = memberMapper.selectById(memberId);
        record(memberId, orderId, orderSn, TYPE_INVALID_BACK, points,
                latest == null ? points : latest.getIntegration(),
                "system", "订单作废退回抵扣积分");
    }

    @Override
    public CommonPage<MemberIntegrationHistory> listHistory(Long memberId, Integer pageNum, Integer pageSize) {
        IPage<MemberIntegrationHistory> page = new Page<>(
                pageNum == null ? 1 : pageNum, pageSize == null ? 10 : pageSize);
        LambdaQueryWrapper<MemberIntegrationHistory> w = new LambdaQueryWrapper<>();
        w.eq(MemberIntegrationHistory::getMemberId, memberId)
                .orderByDesc(MemberIntegrationHistory::getCreateTime)
                .orderByDesc(MemberIntegrationHistory::getId);
        return CommonPage.restPage(historyMapper.selectPage(page, w));
    }

    private void record(Long memberId, Long orderId, String orderSn, int type, int changeCount,
                        int after, String operateMan, String note) {
        MemberIntegrationHistory h = new MemberIntegrationHistory();
        h.setMemberId(memberId);
        h.setOrderId(orderId);
        h.setOrderSn(orderSn);
        h.setChangeType(type);
        h.setChangeCount(changeCount);
        h.setIntegrationAfter(after);
        h.setOperateMan(operateMan);
        h.setOperateNote(note);
        historyMapper.insert(h);
    }
}
