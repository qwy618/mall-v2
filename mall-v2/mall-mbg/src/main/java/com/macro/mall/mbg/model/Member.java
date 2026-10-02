package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.FieldStrategy;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("member")
public class Member {
    @TableId(type = IdType.AUTO)
    private Long id;
    private String phone;          // 登录名（手机号，唯一）
    private String password;       // BCrypt 加密存储
    private String nickname;
    private String icon;           // 头像 URL（数据库列 icon）
    private Integer status;        // 1 正常 0 禁用
    // ===== 会员成长体系（债务18，DDL 010）=====
    private Long levelId;          // level_id 当前会员等级（member_level.id）
    private Integer integration;   // integration 当前可用积分
    private Integer growth;        // growth 成长值（决定等级，只增不减）
    private Integer historyIntegration; // history_integration 累计获得积分（只增不减）
    // create_time / update_time 由数据库默认值维护；插入时不传，避免 NOT NULL 报错
    @TableField(insertStrategy = FieldStrategy.NOT_NULL)
    private LocalDateTime createTime;
}
