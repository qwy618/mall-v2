package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.macro.mall.admin.dto.RoleMenuUpdateParam;
import com.macro.mall.admin.dto.UmsRoleDTO;
import com.macro.mall.admin.service.RoleService;
import com.macro.mall.common.ResultCode;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.UmsAdminRoleRelationMapper;
import com.macro.mall.mbg.mapper.UmsRoleMapper;
import com.macro.mall.mbg.model.UmsAdminRoleRelation;
import com.macro.mall.mbg.model.UmsRole;
import org.springframework.beans.BeanUtils;
import java.util.List;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.stream.Collectors;

@Service
public class RoleServiceImpl implements RoleService {

    @Autowired
    private UmsRoleMapper umsRoleMapper;
    @Autowired
    private UmsAdminRoleRelationMapper adminRoleRelationMapper;

    @Override
    public List<UmsRole> listAll() {
        return umsRoleMapper.selectList(
                new LambdaQueryWrapper<UmsRole>().orderByAsc(UmsRole::getSort));
    }

    @Override
    @Transactional
    public Long createRole(UmsRoleDTO dto) {
        UmsRole role = new UmsRole();
        BeanUtils.copyProperties(dto, role);   // 拷贝 id/name/code/description/status/sort
        role.setMenuIds(null);                  // 新建不带入菜单，后续在角色页勾选
        umsRoleMapper.insert(role);
        return role.getId();
    }

    @Override
    @Transactional
    public Long updateRole(UmsRoleDTO dto) {
        UmsRole role = umsRoleMapper.selectById(dto.getId());
        if (role == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "角色不存在");
        }
        BeanUtils.copyProperties(dto, role);    // DTO 不含 menuIds，故不会被覆盖
        umsRoleMapper.updateById(role);
        return role.getId();
    }

    @Override
    @Transactional
    public Long deleteRole(Long id) {
        UmsRole role = umsRoleMapper.selectById(id);
        if (role == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "角色不存在");
        }
        Long used = adminRoleRelationMapper.selectCount(
                new LambdaQueryWrapper<UmsAdminRoleRelation>().eq(UmsAdminRoleRelation::getRoleId, id));
        if (used != null && used > 0) {
            throw new BusinessException(ResultCode.FAILED, "该角色已分配给管理员，无法删除");
        }
        umsRoleMapper.deleteById(id);
        return id;
    }

    @Override
    @Transactional
    public Long updateMenus(RoleMenuUpdateParam param) {
        UmsRole role = umsRoleMapper.selectById(param.getRoleId());
        if (role == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "角色不存在");
        }
        String joined = (param.getMenuIds() == null || param.getMenuIds().isEmpty())
                ? null
                : param.getMenuIds().stream()
                .filter(StringUtils::hasText)
                .collect(Collectors.joining(","));
        role.setMenuIds(joined);
        umsRoleMapper.updateById(role);
        return role.getId();
    }
}
