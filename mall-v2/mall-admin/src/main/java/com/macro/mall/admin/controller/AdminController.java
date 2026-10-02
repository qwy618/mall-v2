package com.macro.mall.admin.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.macro.mall.admin.dto.AdminLoginParam;
import com.macro.mall.admin.dto.AdminRoleUpdateParam;
import com.macro.mall.admin.dto.UmsAdminDTO;
import com.macro.mall.admin.dto.UpdateStatusParam;
import com.macro.mall.admin.service.AdminService;
import com.macro.mall.admin.vo.AdminInfoVO;
import com.macro.mall.admin.vo.AdminListItemVO;
import com.macro.mall.admin.vo.AdminLoginVO;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/admin")
public class AdminController {

    @Autowired
    private AdminService adminService;

    @PostMapping("/login")
    public CommonResult<AdminLoginVO> login(@RequestBody @Valid AdminLoginParam param) {
        return CommonResult.success(adminService.login(param));
    }

    @PostMapping("/info")
    public CommonResult<AdminInfoVO> info() {
        return CommonResult.success(adminService.info());
    }

    // ===================== 用户管理（RBAC） =====================

    @GetMapping("/list")
    public CommonResult<CommonPage<AdminListItemVO>> list(
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize) {
        IPage<AdminListItemVO> page = adminService.listAdmins(keyword, pageNum, pageSize);
        return CommonResult.success(CommonPage.restPage(page));
    }

    @PostMapping("/create")
    public CommonResult<Long> create(@RequestBody @Valid UmsAdminDTO dto) {
        return CommonResult.success(adminService.createAdmin(dto));
    }

    @PostMapping("/update")
    public CommonResult<Long> update(@RequestBody @Valid UmsAdminDTO dto) {
        return CommonResult.success(adminService.updateAdmin(dto));
    }

    @PostMapping("/delete/{id}")
    public CommonResult<Long> delete(@PathVariable Long id) {
        return CommonResult.success(adminService.deleteAdmin(id));
    }

    @PostMapping("/updateStatus/{id}")
    public CommonResult<Long> updateStatus(@PathVariable Long id,
                                          @RequestBody @Valid UpdateStatusParam param) {
        return CommonResult.success(adminService.updateAdminStatus(id, param.getStatus()));
    }

    /** 分配管理员角色 */
    @PostMapping("/role/update")
    public CommonResult<Long> updateRole(@RequestBody @Valid AdminRoleUpdateParam param) {
        return CommonResult.success(adminService.assignRoles(param));
    }

    /** 查询某管理员已分配角色 id 列表 */
    @GetMapping("/role/{adminId}")
    public CommonResult<List<Long>> getRoles(@PathVariable Long adminId) {
        return CommonResult.success(adminService.getRoleIds(adminId));
    }
}
