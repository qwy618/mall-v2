package com.macro.mall.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.macro.mall.mbg.mapper.MemberLevelMapper;
import com.macro.mall.mbg.model.Member;
import com.macro.mall.mbg.model.MemberLevel;
import com.macro.mall.service.MemberLevelService;
import com.macro.mall.service.vo.MemberLevelVO;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class MemberLevelServiceImpl implements MemberLevelService {

    private final MemberLevelMapper memberLevelMapper;

    public MemberLevelServiceImpl(MemberLevelMapper memberLevelMapper) {
        this.memberLevelMapper = memberLevelMapper;
    }

    @Override
    public List<MemberLevel> listAll() {
        return memberLevelMapper.selectList(new LambdaQueryWrapper<MemberLevel>()
                .orderByAsc(MemberLevel::getGrowthPoint));
    }

    @Override
    public MemberLevel matchByGrowth(Integer growth) {
        int g = growth == null ? 0 : growth;
        return memberLevelMapper.selectOne(new LambdaQueryWrapper<MemberLevel>()
                .le(MemberLevel::getGrowthPoint, g)
                .orderByDesc(MemberLevel::getGrowthPoint)
                .last("limit 1"));
    }

    @Override
    public MemberLevelVO buildVO(Member member) {
        int growth = member == null || member.getGrowth() == null ? 0 : member.getGrowth();
        List<MemberLevel> levels = listAll();

        MemberLevel current = null;
        MemberLevel next = null;
        for (MemberLevel lv : levels) {
            if (lv.getGrowthPoint() != null && lv.getGrowthPoint() <= growth) {
                current = lv;
            } else {
                next = lv;
                break;
            }
        }
        if (current == null && !levels.isEmpty()) {
            current = levels.get(0);   // 兜底：等级表异常时按最低档展示
        }

        MemberLevelVO vo = new MemberLevelVO();
        vo.setLevelId(current == null ? null : current.getId());
        vo.setLevelName(current == null ? "普通会员" : current.getName());
        vo.setIntegrationRate(current == null ? 100 : current.getIntegrationRate());
        vo.setDiscountRate(current == null ? 100 : current.getDiscountRate());
        vo.setGrowth(growth);
        vo.setIntegration(member == null || member.getIntegration() == null ? 0 : member.getIntegration());
        vo.setHistoryIntegration(member == null || member.getHistoryIntegration() == null
                ? 0 : member.getHistoryIntegration());

        if (next != null) {
            int base = current == null || current.getGrowthPoint() == null ? 0 : current.getGrowthPoint();
            int span = next.getGrowthPoint() - base;
            int done = growth - base;
            vo.setNextLevelName(next.getName());
            vo.setNextGrowthPoint(next.getGrowthPoint());
            vo.setGrowthGap(Math.max(0, next.getGrowthPoint() - growth));
            vo.setProgress(span <= 0 ? 100
                    : Math.max(0, Math.min(100, (int) Math.round(done * 100.0 / span))));
        } else {
            vo.setProgress(100);   // 已是最高等级
        }
        return vo;
    }
}
