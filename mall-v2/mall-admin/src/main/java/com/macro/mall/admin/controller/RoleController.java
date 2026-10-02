package com.macro.mall.admin.controller;

import com.macro.mall.admin.dto.RoleMenuUpdateParam;
import com.macro.mall.admin.dto.UmsRoleDTO;
import com.macro.mall.admin.service.RoleService;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.UmsRole;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/role")
public class RoleController {

    @Autowired
    private RoleService roleService;

    /** GET /role/list —— 角色管理页初始化，返回全部角色（含 menuIds） */
    @GetMapping("/list")
    public CommonResult<List<UmsRole>> list() {
        return CommonResult.success(roleService.listAll());
    }

    @PostMapping("/create")
    public CommonResult<Long> create(@RequestBody @Valid UmsRoleDTO dto) {
        return CommonResult.success(roleService.createRole(dto));
    }

    @PostMapping("/update")
    public CommonResult<Long> update(@RequestBody @Valid UmsRoleDTO dto) {
        return CommonResult.success(roleService.updateRole(dto));
    }

    /** POST /role/delete/{id} —— 已分配管理员的角色会被拒绝 */
    @PostMapping("/delete/{id}")
    public CommonResult<Long> delete(@PathVariable Long id) {
        return CommonResult.success(roleService.deleteRole(id));
    }

    /** POST /role/updateMenus —— 保存勾选的菜单（前端路由 name 数组） */
    @PostMapping("/updateMenus")
    public CommonResult<Long> updateMenus(@RequestBody @Valid RoleMenuUpdateParam param) {
        return CommonResult.success(roleService.updateMenus(param));
    }
}
