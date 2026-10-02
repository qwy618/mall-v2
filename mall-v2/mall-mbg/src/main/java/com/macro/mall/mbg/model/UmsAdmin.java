package com.macro.mall.mbg.model;

import java.time.LocalDateTime;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

/**
 * 后台管理员。
 *
 * 注意：全局 mybatis-plus 配置了 logic-delete-field=deleteStatus，
 * 本实体没有该字段，所以不会走逻辑删除（管理员用 status 1/0 表示启停，物理删除不用）。
 */
@Data
@TableName("ums_admin")
public class UmsAdmin {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private String username;
    private String password;
    private String icon;
    private String email;
    private String nickName;
    private String note;
    private LocalDateTime createTime;
    private LocalDateTime loginTime;
    /** 账号状态：1-启用 0-禁用 */
    private Integer status;
}
