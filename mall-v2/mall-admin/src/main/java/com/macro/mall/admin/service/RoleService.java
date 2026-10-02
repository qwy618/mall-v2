package com.macro.mall.admin.service;

import com.macro.mall.admin.dto.RoleMenuUpdateParam;
import com.macro.mall.admin.dto.UmsRoleDTO;
import com.macro.mall.mbg.model.UmsRole;

import java.util.List;

public interface RoleService {
    /** 查询全部角色（含各角色 menuIds，菜单选项由前端 routes 生成） */
    List<UmsRole> listAll();

    Long createRole(UmsRoleDTO dto);

    Long updateRole(UmsRoleDTO dto);

    /** 删除角色：若已分配给管理员则拒绝 */
    Long deleteRole(Long id);

    /** 保存角色可见菜单（menuIds 用逗号拼接存库） */
    Long updateMenus(RoleMenuUpdateParam param);
}
