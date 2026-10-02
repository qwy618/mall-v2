package com.macro.mall.service;

import com.macro.mall.mbg.model.Member;
import com.macro.mall.mbg.model.MemberLevel;
import com.macro.mall.service.vo.MemberLevelVO;

import java.util.List;

/**
 * 会员等级（债务18）：等级配置查询 + 成长值匹配 + 个人中心展示模型组装。
 *
 * <p>放在 mall-service 共享模块，admin 与 portal 共同使用：
 * portal 用于个人中心展示与下单折扣；admin 用于退货回冲时按等级倍率换算积分。
 */
public interface MemberLevelService {

    /** 全部等级，按成长值门槛升序 */
    List<MemberLevel> listAll();

    /** 按成长值匹配可享等级：取 growth_point &lt;= growth 的最高档；无配置时返回 null */
    MemberLevel matchByGrowth(Integer growth);

    /** 组装个人中心成长信息（等级名 + 权益 + 进度 + 积分） */
    MemberLevelVO buildVO(Member member);
}
