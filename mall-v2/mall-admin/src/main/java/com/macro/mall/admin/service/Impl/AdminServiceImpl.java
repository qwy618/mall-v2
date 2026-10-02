package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.admin.component.AdminUserDetails;
import com.macro.mall.admin.component.JwtTokenUtil;
import com.macro.mall.admin.dto.AdminLoginParam;
import com.macro.mall.admin.dto.AdminRoleUpdateParam;
import com.macro.mall.admin.dto.UmsAdminDTO;
import com.macro.mall.admin.service.AdminService;
import com.macro.mall.admin.vo.AdminInfoVO;
import com.macro.mall.admin.vo.AdminListItemVO;
import com.macro.mall.admin.vo.AdminLoginVO;
import com.macro.mall.common.ResultCode;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.UmsAdminMapper;
import com.macro.mall.mbg.mapper.UmsAdminRoleRelationMapper;
import com.macro.mall.mbg.mapper.UmsRoleMapper;
import com.macro.mall.mbg.model.UmsAdmin;
import com.macro.mall.mbg.model.UmsAdminRoleRelation;
import com.macro.mall.mbg.model.UmsRole;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class AdminServiceImpl implements AdminService {

    @Value("${jwt.tokenHead}")
    private String tokenHead;

    @Autowired
    private AuthenticationManager authenticationManager;
    @Autowired
    private JwtTokenUtil jwtTokenUtil;
    @Autowired
    private UserDetailsService userDetailsService;
    @Autowired
    private UmsAdminMapper umsAdminMapper;
    @Autowired
    private UmsAdminRoleRelationMapper adminRoleRelationMapper;
    @Autowired
    private UmsRoleMapper umsRoleMapper;
    @Autowired
    private PasswordEncoder passwordEncoder;

    // ===================== 登录 / 信息 =====================

    @Override
    public AdminLoginVO login(AdminLoginParam param) {
        Authentication authentication;
        try {
            authentication = authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(param.getUsername(), param.getPassword()));
        } catch (AuthenticationException e) {
            throw new BusinessException("用户名或密码错误");
        }
        String token = jwtTokenUtil.generateToken(param.getUsername());
        return new AdminLoginVO(token, tokenHead);
    }

    @Override
    public AdminInfoVO info() {
        AdminUserDetails details = (AdminUserDetails) SecurityContextHolder.getContext()
                .getAuthentication().getPrincipal();
        if (details == null) {
            throw new BusinessException("用户未登录");
        }
        UmsAdmin admin = details.getAdmin();
        AdminInfoVO vo = new AdminInfoVO();
        BeanUtils.copyProperties(admin, vo);

        // 角色 code 列表
        List<String> roleCodes = details.getRoles().stream()
                .map(UmsRole::getCode)
                .collect(Collectors.toList());
        vo.setRoles(roleCodes);

        // menuIds = 各角色 menu_ids 逗号拆分后并集去重（超级管理员为空 -> 前端短路全可见）
        Set<String> menuSet = new LinkedHashSet<>();
        details.getRoles().forEach(r -> {
            if (StringUtils.hasText(r.getMenuIds())) {
                for (String m : r.getMenuIds().split(",")) {
                    if (StringUtils.hasText(m)) {
                        menuSet.add(m.trim());
                    }
                }
            }
        });
        vo.setMenuIds(new ArrayList<>(menuSet));
        return vo;
    }

    // ===================== 管理员分页列表 =====================

    @Override
    public IPage<AdminListItemVO> listAdmins(String keyword, int pageNum, int pageSize) {
        LambdaQueryWrapper<UmsAdmin> w = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(keyword)) {
            w.like(UmsAdmin::getUsername, keyword).or().like(UmsAdmin::getNickName, keyword);
        }
        w.orderByDesc(UmsAdmin::getId);
        IPage<UmsAdmin> page = umsAdminMapper.selectPage(new Page<>(pageNum, pageSize), w);

        List<UmsAdmin> records = page.getRecords();
        Map<Long, List<String>> rolesOfAdmin = new HashMap<>();
        if (!records.isEmpty()) {
            List<Long> adminIds = records.stream().map(UmsAdmin::getId).collect(Collectors.toList());

            // 1) adminId -> roleIds（批量查，避免 N+1）
            Map<Long, List<Long>> roleIdsOfAdmin = adminRoleRelationMapper
                    .selectList(new LambdaQueryWrapper<UmsAdminRoleRelation>()
                            .in(UmsAdminRoleRelation::getAdminId, adminIds))
                    .stream()
                    .collect(Collectors.groupingBy(UmsAdminRoleRelation::getAdminId,
                            Collectors.mapping(UmsAdminRoleRelation::getRoleId, Collectors.toList())));

            // 2) roleId -> code
            Set<Long> allRoleIds = roleIdsOfAdmin.values().stream()
                    .flatMap(List::stream).collect(Collectors.toSet());
            Map<Long, String> roleCodeMap = new HashMap<>();
            if (!allRoleIds.isEmpty()) {
                umsRoleMapper.selectBatchIds(allRoleIds)
                        .forEach(r -> roleCodeMap.put(r.getId(), r.getCode()));
            }

            // 3) 组装每个管理员的角色 code 列表
            for (UmsAdmin a : records) {
                List<Long> rids = roleIdsOfAdmin.getOrDefault(a.getId(), Collections.emptyList());
                List<String> codes = rids.stream().map(roleCodeMap::get)
                        .filter(Objects::nonNull).collect(Collectors.toList());
                rolesOfAdmin.put(a.getId(), codes);
            }
        }

        List<AdminListItemVO> vos = records.stream().map(a -> {
            AdminListItemVO vo = new AdminListItemVO();
            BeanUtils.copyProperties(a, vo);
            vo.setRoles(rolesOfAdmin.getOrDefault(a.getId(), Collections.emptyList()));
            return vo;
        }).collect(Collectors.toList());

        IPage<AdminListItemVO> result = new Page<>(pageNum, pageSize);
        result.setRecords(vos);
        result.setTotal(page.getTotal());
        return result;
    }

    // ===================== 管理员 CRUD =====================

    @Override
    @Transactional
    public Long createAdmin(UmsAdminDTO dto) {
        if (umsAdminMapper.selectCount(new LambdaQueryWrapper<UmsAdmin>()
                .eq(UmsAdmin::getUsername, dto.getUsername())) > 0) {
            throw new BusinessException(ResultCode.VALIDATE_FAILED, "用户名已存在");
        }
        UmsAdmin admin = new UmsAdmin();
        admin.setUsername(dto.getUsername());
        admin.setNickName(dto.getNickName());
        admin.setEmail(dto.getEmail());
        admin.setStatus(dto.getStatus() == null ? 1 : dto.getStatus());
        admin.setPassword(passwordEncoder.encode(dto.getPassword()));
        admin.setCreateTime(LocalDateTime.now());
        umsAdminMapper.insert(admin);
        return admin.getId();
    }

    @Override
    @Transactional
    public Long updateAdmin(UmsAdminDTO dto) {
        UmsAdmin admin = umsAdminMapper.selectById(dto.getId());
        if (admin == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "管理员不存在");
        }
        if (StringUtils.hasText(dto.getNickName())) admin.setNickName(dto.getNickName());
        if (StringUtils.hasText(dto.getEmail())) admin.setEmail(dto.getEmail());
        if (dto.getStatus() != null) admin.setStatus(dto.getStatus());
        if (StringUtils.hasText(dto.getPassword())) {
            admin.setPassword(passwordEncoder.encode(dto.getPassword()));
        }
        umsAdminMapper.updateById(admin);
        return admin.getId();
    }

    @Override
    @Transactional
    public Long deleteAdmin(Long id) {
        UmsAdmin admin = umsAdminMapper.selectById(id);
        if (admin == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "管理员不存在");
        }
        if ("admin".equals(admin.getUsername())) {
            throw new BusinessException(ResultCode.FAILED, "不能删除超级管理员");
        }
        // 先清角色关联，再删管理员（物理删除，ums_admin 无 deleteStatus 字段）
        adminRoleRelationMapper.delete(new LambdaQueryWrapper<UmsAdminRoleRelation>()
                .eq(UmsAdminRoleRelation::getAdminId, id));
        umsAdminMapper.deleteById(id);
        return id;
    }

    @Override
    @Transactional
    public Long updateAdminStatus(Long id, Integer status) {
        UmsAdmin admin = umsAdminMapper.selectById(id);
        if (admin == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "管理员不存在");
        }
        admin.setStatus(status);
        umsAdminMapper.updateById(admin);
        return id;
    }

    // ===================== 管理员 ↔ 角色 =====================

    @Override
    @Transactional
    public Long assignRoles(AdminRoleUpdateParam param) {
        Long adminId = param.getAdminId();
        // 清旧
        adminRoleRelationMapper.delete(new LambdaQueryWrapper<UmsAdminRoleRelation>()
                .eq(UmsAdminRoleRelation::getAdminId, adminId));
        // 写新
        List<Long> roleIds = param.getRoleIds() == null ? Collections.emptyList() : param.getRoleIds();
        for (Long roleId : roleIds) {
            UmsAdminRoleRelation r = new UmsAdminRoleRelation();
            r.setAdminId(adminId);
            r.setRoleId(roleId);
            adminRoleRelationMapper.insert(r);
        }
        return adminId;
    }

    @Override
    public List<Long> getRoleIds(Long adminId) {
        return adminRoleRelationMapper.selectList(new LambdaQueryWrapper<UmsAdminRoleRelation>()
                .eq(UmsAdminRoleRelation::getAdminId, adminId))
                .stream().map(UmsAdminRoleRelation::getRoleId).collect(Collectors.toList());
    }
}
