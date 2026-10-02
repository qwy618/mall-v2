package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 会员等级配置（债务18，DDL 010 落库）。
 * 等级由成长值决定：取 growth_point &lt;= 当前成长值 的最高档。
 */
@Data
@TableName("member_level")
public class MemberLevel {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String name;            // 等级名称
    private Integer growthPoint;    // 达到该成长值即此等级（含）
    private Integer integrationRate;// 下单赠送积分倍率(%)：100=1倍 150=1.5倍
    private Integer discountRate;   // 会员折扣(%)：100=原价 98=98折
    private String note;            // 权益说明
    private LocalDateTime createTime;
}
