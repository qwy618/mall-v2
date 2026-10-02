package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.macro.mall.admin.component.AdminUserDetails;
import com.macro.mall.mbg.mapper.UmsAdminMapper;
import com.macro.mall.mbg.mapper.UmsAdminRoleRelationMapper;
import com.macro.mall.mbg.mapper.UmsRoleMapper;
import com.macro.mall.mbg.model.UmsAdmin;
import com.macro.mall.mbg.model.UmsAdminRoleRelation;
import com.macro.mall.mbg.model.UmsRole;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class UserDetailsServiceImpl implements UserDetailsService {
    private final UmsAdminMapper umsAdminMapper;
    private final UmsAdminRoleRelationMapper umsAdminRoleRelationMapper;
    private final UmsRoleMapper umsRoleMapper;
    public UserDetailsServiceImpl(UmsAdminMapper umsAdminMapper, UmsAdminRoleRelationMapper umsAdminRoleRelationMapper, UmsRoleMapper umsRoleMapper) {
        this.umsAdminMapper = umsAdminMapper;
        this.umsAdminRoleRelationMapper = umsAdminRoleRelationMapper;
        this.umsRoleMapper = umsRoleMapper;
    }

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        //1. 根据用户名查询用户
        UmsAdmin umsAdmin = umsAdminMapper.selectOne(
                new LambdaQueryWrapper<UmsAdmin>().eq(UmsAdmin::getUsername, username)
        );
        if (umsAdmin == null) {
            throw new UsernameNotFoundException("User not found");
        }
        //2. 根据用户查询用户角色
        List<UmsAdminRoleRelation> umsAdminRoleRelations = umsAdminRoleRelationMapper.selectList(new LambdaQueryWrapper<UmsAdminRoleRelation>().eq(UmsAdminRoleRelation::getAdminId, umsAdmin.getId()));
        //3. 根据角色id来查询角色
        List<UmsRole> roles = umsAdminRoleRelations.stream()
                .map(r -> umsRoleMapper.selectById(r.getRoleId()))
                .filter(Objects::nonNull)
                .collect(Collectors.toList());

        //4. 计算所有角色 menu_ids 的并集去重（与 AdminServiceImpl.info() 算法保持一致）
        Set<String> menuSet = new LinkedHashSet<>();
        for (UmsRole role : roles) {
            String menuIds = role.getMenuIds();
            if (menuIds != null && !menuIds.isBlank()) {
                for (String s : menuIds.split(",")) {
                    String t = s.trim();
                    if (!t.isEmpty()) {
                        menuSet.add(t);
                    }
                }
            }
        }
        List<String> menuIdList = new ArrayList<>(menuSet);

        return new AdminUserDetails(umsAdmin, roles, menuIdList);
    }
}
