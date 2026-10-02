package com.macro.mall.admin.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.macro.mall.admin.dto.AdminLoginParam;
import com.macro.mall.admin.dto.AdminRoleUpdateParam;
import com.macro.mall.admin.dto.UmsAdminDTO;
import com.macro.mall.admin.vo.AdminInfoVO;
import com.macro.mall.admin.vo.AdminListItemVO;
import com.macro.mall.admin.vo.AdminLoginVO;

import java.util.List;

public interface AdminService {
    AdminLoginVO login(AdminLoginParam param);

    AdminInfoVO info();

    /** 分页查询管理员，每项附带角色 code 数组 */
    IPage<AdminListItemVO> listAdmins(String keyword, int pageNum, int pageSize);

    Long createAdmin(UmsAdminDTO dto);

    Long updateAdmin(UmsAdminDTO dto);

    /** 删除管理员：不允许删除 super admin(username=admin) */
    Long deleteAdmin(Long id);

    Long updateAdminStatus(Long id, Integer status);

    /** 重新分配某管理员的角色（先清后写） */
    Long assignRoles(AdminRoleUpdateParam param);

    /** 查询某管理员已分配的角色 id 列表 */
    List<Long> getRoleIds(Long adminId);
}
