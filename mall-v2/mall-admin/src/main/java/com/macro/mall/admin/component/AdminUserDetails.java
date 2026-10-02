package com.macro.mall.admin.component;

import com.macro.mall.mbg.model.UmsAdmin;
import com.macro.mall.mbg.model.UmsRole;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

public class AdminUserDetails implements UserDetails {
    private UmsAdmin umsAdmin;
    private List<UmsRole> roles;
    private List<String> menuIds;

    public AdminUserDetails(UmsAdmin umsAdmin, List<UmsRole> roles) {
        this(umsAdmin, roles, Collections.emptyList());
    }

    public AdminUserDetails(UmsAdmin umsAdmin, List<UmsRole> roles, List<String> menuIds) {
        this.umsAdmin = umsAdmin;
        this.roles = roles;
        this.menuIds = menuIds != null ? menuIds : Collections.emptyList();
    }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return roles.stream().map(role -> new SimpleGrantedAuthority("ROLE_" +role.getCode())).collect(Collectors.toList());
    }

    @Override
    public String getPassword() {
        return umsAdmin.getPassword();
    }

    @Override
    public String getUsername() {
        return umsAdmin.getUsername();
    }
    /**
     * 账号是否未过期
     */
    @Override
    public boolean isAccountNonExpired() {
        return true;
    }

    public List<UmsRole> getRoles() {
        return roles;
    }

    public List<String> getMenuIds() {
        return menuIds;
    }

    /**
     * 账号是否未锁定
     */
    @Override
    public boolean isAccountNonLocked() {
        return true;
    }

    /**
     * 密码是否未过期
     */
    @Override
    public boolean isCredentialsNonExpired() {
        return true;
    }

    /**
     * 账号是否启用
     */
    @Override
    public boolean isEnabled() {
        return umsAdmin.getStatus() == 1;
    }

    /**
     * 获取管理员实体（方便后续使用）
     */
    public UmsAdmin getAdmin() {
        return umsAdmin;
    }
}
