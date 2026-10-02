package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("ums_admin_role_relation")
public class UmsAdminRoleRelation {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long adminId;   // 对应列 admin_id（mybatis-plus 下划线转驼峰，自动映射）
    private Long roleId;   // 对应列 role_id
}
