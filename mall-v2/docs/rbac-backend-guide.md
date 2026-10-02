# mall-v2 后台 RBAC 后端实现指南（P0）

> 前端已就绪：mall-admin-v2 的用户管理 / 角色管理页、权限链、数据库 DDL 均已落盘并通过 `vue-tsc -b` + `vite build`。
> 本文档是后端落地指引（设计 + 接口契约 + 伪代码），按项目红线由你手写 Java，写完贴来 AI 审查。
> 所有接口路径、参数、返回结构都已与前端 `mall-admin-v2/src/apis/admin.ts` + `src/types/admin.ts` 逐字段对齐，照着写即可零偏差。

---

## 0. 文件操作清单

**修改**
- `mall-mbg/.../model/UmsRole.java`：补 `menuIds` 字段（推荐重跑 MBG 生成，最干净）
- `mall-admin/.../vo/AdminInfoVO.java`：补 `menuIds` 字段
- `mall-admin/.../service/AdminService.java`：扩展接口方法
- `mall-admin/.../service/Impl/AdminServiceImpl.java`：实现
- `mall-admin/.../controller/AdminController.java`：扩展接口
- `mall-admin/.../config/SecurityConfig.java`：加接口级鉴权
- （建议）`mall-admin/.../dto/` 下新建 `UmsAdminDTO` / `AdminRoleUpdateParam` / `RoleMenuUpdateParam`

**新建**
- `mall-admin/.../controller/RoleController.java`
- `mall-admin/.../service/RoleService.java` + `Impl/RoleServiceImpl.java`

**不用改**（已确认）
- `UserDetailsServiceImpl`（已加载 `List<UmsRole>` 注入 `AdminUserDetails`）
- `JwtAuthenticationTokenFilter`（第 48–51 行已把 `ROLE_<code>` 注入 SecurityContext → 后端 `hasRole` 直接可用）
- `AdminUserDetails`（已有 `getRoles()`）

---

## 1. 执行 DDL（已写盘，你只需跑一次）

文件：`mall-v2/sql/rbac_role_menu_ids.sql`

```bash
mysql -u root -p mall_v2 < mall-v2/sql/rbac_role_menu_ids.sql
```

作用：
- 幂等 `ALTER TABLE ums_role ADD COLUMN menu_ids VARCHAR(500)`
- 给 `product` 角色预置 `menu_ids = 'Dashboard,Brand,Category,Product,Order,Coupon'`（与前端路由 name 完全一致、不含 System）
- `admin` 角色 `menu_ids` 留空 → 前端 `canAccess` 短路全可见

---

## 2. UmsRole 实体补 menuIds

- **推荐**：重跑 MBG → `UmsRole` 自动多出 `private String menuIds;`
- **或手写**：在 `model/UmsRole.java` 加 `private String menuIds;`（实体已有 `@Data`，getter/setter 自动生成；下次重跑 MBG 会覆盖，学习项目可接受）

---

## 3. AdminInfoVO 补 menuIds

```java
@Data
public class AdminInfoVO {
    private String username;
    private String nickName;
    private String icon;
    private String email;
    private List<String> roles;     // 角色 code 列表（已有）
    private List<String> menuIds;   // ← 新增：角色可见菜单并集（前端路由 name）
}
```

---

## 4. DTO（放 mall-admin 的 dto 包）

```java
// UmsAdminDTO（新建/编辑管理员）
@Data
public class UmsAdminDTO {
    private Long id;
    private String username;
    private String password;   // 新建必填；编辑时为空 = 不改密码
    private String nickName;
    private String email;
    private Integer status;
    private List<Long> roleIds; // 分配的角色 id 列表
}

// AdminRoleUpdateParam（分配角色）
@Data
public class AdminRoleUpdateParam {
    private Long adminId;
    private List<Long> roleIds;
}

// RoleMenuUpdateParam（分配角色可见菜单）
@Data
public class RoleMenuUpdateParam {
    private Long roleId;
    private List<String> menuIds; // 前端路由 name 数组
}
```

> 注：前端 `UmsRoleDTO` 不含 `menuIds`，角色的菜单通过独立的 `updateMenus` 接口保存，不随 create/update 传。

---

## 5. AdminService 接口扩展

```java
public interface AdminService {
    AdminLoginVO login(AdminLoginParam param);
    AdminInfoVO info();

    // 用户管理
    CommonPage<UmsAdminListItem> list(String keyword, Integer pageNum, Integer pageSize);
    Long create(UmsAdminDTO dto);
    int update(UmsAdminDTO dto);
    int delete(Long id);
    int updateStatus(Long id, Integer status);

    // 角色分配
    int assignRoles(Long adminId, List<Long> roleIds);
    List<Long> getRoleIds(Long adminId);
}
```

> `UmsAdminListItem`：可以是 `UmsAdmin` 的子类或新 VO，在 `UmsAdmin` 基础上额外带 `List<String> roles`（角色 code 数组）。前端列表项类型 `UmsAdmin` 已有 `roles?: string[]` 字段，字段名对齐即可。

---

## 6. AdminServiceImpl 实现要点（伪代码）

**已有注入**：`UmsAdminMapper umsAdminMapper`、`PasswordEncoder passwordEncoder`、再加 `UmsAdminRoleRelationMapper`、`UmsRoleMapper`。

### 6.1 list（分页 + 每项带 roles）

```java
public CommonPage<UmsAdminListItem> list(String keyword, int pageNum, int pageSize) {
    Page<UmsAdmin> page = umsAdminMapper.selectPage(
        new Page<>(pageNum, pageSize),
        new LambdaQueryWrapper<UmsAdmin>()
            .like(StringUtils.hasText(keyword), UmsAdmin::getUsername, keyword)
            .or().like(StringUtils.hasText(keyword), UmsAdmin::getNickName, keyword)
            .orderByDesc(UmsAdmin::getCreateTime));
    List<UmsAdminListItem> items = page.getRecords().stream().map(a -> {
        UmsAdminListItem it = new UmsAdminListItem();
        BeanUtils.copyProperties(a, it);
        it.setRoles(loadRoleCodes(a.getId()));
        return it;
    }).collect(Collectors.toList());
    return new CommonPage<>(items, page.getTotal());
}

// 查某 admin 的角色 code 列表（列表项展示用）
private List<String> loadRoleCodes(Long adminId) {
    return umsAdminRoleRelationMapper
        .selectList(new LambdaQueryWrapper<UmsAdminRoleRelation>()
            .eq(UmsAdminRoleRelation::getAdminId, adminId))
        .stream()
        .map(r -> umsRoleMapper.selectById(r.getRoleId()))
        .filter(Objects::nonNull)
        .map(UmsRole::getCode)
        .collect(Collectors.toList());
}
```

### 6.2 create（BCrypt 加密 + 写 admin + 写关联）

```java
public Long create(UmsAdminDTO dto) {
    if (umsAdminMapper.selectCount(new LambdaQueryWrapper<UmsAdmin>()
            .eq(UmsAdmin::getUsername, dto.getUsername())) > 0)
        throw new BusinessException("用户名已存在");
    UmsAdmin admin = new UmsAdmin();
    BeanUtils.copyProperties(dto, admin);
    admin.setPassword(passwordEncoder.encode(dto.getPassword()));
    admin.setCreateTime(LocalDateTime.now());
    umsAdminMapper.insert(admin);
    saveRoleRelations(admin.getId(), dto.getRoleIds());
    return admin.getId();
}
```

### 6.3 update（密码非空才改 + 角色先删后插）

```java
public int update(UmsAdminDTO dto) {
    UmsAdmin admin = new UmsAdmin();
    BeanUtils.copyProperties(dto, admin);
    if (dto.getPassword() != null && !dto.getPassword().isEmpty())
        admin.setPassword(passwordEncoder.encode(dto.getPassword()));
    else admin.setPassword(null); // 不更新密码列
    int n = umsAdminMapper.updateById(admin);
    saveRoleRelations(dto.getId(), dto.getRoleIds()); // 先删后插
    return n;
}

private void saveRoleRelations(Long adminId, List<Long> roleIds) {
    umsAdminRoleRelationMapper.delete(new LambdaQueryWrapper<UmsAdminRoleRelation>()
        .eq(UmsAdminRoleRelation::getAdminId, adminId));
    if (roleIds != null) roleIds.forEach(rid -> {
        UmsAdminRoleRelation r = new UmsAdminRoleRelation();
        r.setAdminId(adminId); r.setRoleId(rid);
        umsAdminRoleRelationMapper.insert(r);
    });
}
```

### 6.4 delete（物理删 + 防误删 admin）

```java
public int delete(Long id) {
    UmsAdmin a = umsAdminMapper.selectById(id);
    if (a != null && "admin".equals(a.getUsername()))
        throw new BusinessException("不能删除超级管理员账号");
    umsAdminRoleRelationMapper.delete(new LambdaQueryWrapper<UmsAdminRoleRelation>()
        .eq(UmsAdminRoleRelation::getAdminId, id)); // 先清关联
    return umsAdminMapper.deleteById(id);
}
```

### 6.5 updateStatus / assignRoles / getRoleIds

```java
public int updateStatus(Long id, Integer status) {
    UmsAdmin a = new UmsAdmin();
    a.setId(id); a.setStatus(status);
    return umsAdminMapper.updateById(a);
}
public int assignRoles(Long adminId, List<Long> roleIds) {
    saveRoleRelations(adminId, roleIds);
    return roleIds == null ? 0 : roleIds.size();
}
public List<Long> getRoleIds(Long adminId) {
    return umsAdminRoleRelationMapper
        .selectList(new LambdaQueryWrapper<UmsAdminRoleRelation>()
            .eq(UmsAdminRoleRelation::getAdminId, adminId))
        .stream().map(UmsAdminRoleRelation::getRoleId)
        .collect(Collectors.toList());
}
```

### 6.6 info（关键：返回 roles + menuIds 并集）

```java
public AdminInfoVO info() {
    AdminUserDetails details = (AdminUserDetails) SecurityContextHolder
        .getContext().getAuthentication().getPrincipal();
    AdminInfoVO vo = new AdminInfoVO();
    BeanUtils.copyProperties(details.getAdmin(), vo);
    List<UmsRole> roles = details.getRoles();
    vo.setRoles(roles.stream().map(UmsRole::getCode).collect(Collectors.toList()));
    // menuIds = 所有角色 menu_ids 逗号 split 的并集（去重保序）
    Set<String> menuSet = new LinkedHashSet<>();
    roles.forEach(r -> {
        if (r.getMenuIds() != null && !r.getMenuIds().isEmpty())
            Arrays.stream(r.getMenuIds().split(","))
                  .map(String::trim).filter(s -> !s.isEmpty())
                  .forEach(menuSet::add);
    });
    vo.setMenuIds(new ArrayList<>(menuSet));
    return vo;
}
```

---

## 7. AdminController 扩展

```java
@RestController
@RequestMapping("/admin")
public class AdminController {
    @Autowired private AdminService adminService;

    // 现有 login / info 保留
    @PostMapping("/info")
    public CommonResult<AdminInfoVO> info() {
        return CommonResult.success(adminService.info());
    }

    @GetMapping("/list")
    public CommonResult<CommonPage<UmsAdminListItem>> list(
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize) {
        return CommonResult.success(adminService.list(keyword, pageNum, pageSize));
    }

    @PostMapping("/create")
    public CommonResult<Long> create(@RequestBody UmsAdminDTO dto) {
        return CommonResult.success(adminService.create(dto));
    }

    @PostMapping("/update")
    public CommonResult<Integer> update(@RequestBody UmsAdminDTO dto) {
        return CommonResult.success(adminService.update(dto));
    }

    @PostMapping("/delete/{id}")
    public CommonResult<Integer> delete(@PathVariable Long id) {
        return CommonResult.success(adminService.delete(id));
    }

    // 前端发的是 body {status}，用 @RequestBody 接（也可改 @RequestParam，二选一对齐）
    @PostMapping("/updateStatus/{id}")
    public CommonResult<Integer> updateStatus(@PathVariable Long id,
            @RequestBody Map<String, Integer> body) {
        return CommonResult.success(adminService.updateStatus(id, body.get("status")));
    }

    @PostMapping("/role/update")
    public CommonResult<Integer> assignRoles(@RequestBody AdminRoleUpdateParam p) {
        return CommonResult.success(adminService.assignRoles(p.getAdminId(), p.getRoleIds()));
    }

    @GetMapping("/role/{adminId}")
    public CommonResult<List<Long>> getRoles(@PathVariable Long adminId) {
        return CommonResult.success(adminService.getRoleIds(adminId));
    }
}
```

---

## 8. RoleController + RoleService（新建）

```java
@RestController
@RequestMapping("/role")
public class RoleController {
    @Autowired private RoleService roleService;

    @GetMapping("/list")
    public CommonResult<List<UmsRole>> list() {
        return CommonResult.success(roleService.list());
    }
    @PostMapping("/create")
    public CommonResult<Long> create(@RequestBody UmsRoleDTO dto) {
        return CommonResult.success(roleService.create(dto));
    }
    @PostMapping("/update")
    public CommonResult<Integer> update(@RequestBody UmsRoleDTO dto) {
        return CommonResult.success(roleService.update(dto));
    }
    @PostMapping("/delete/{id}")
    public CommonResult<Integer> delete(@PathVariable Long id) {
        return CommonResult.success(roleService.delete(id));
    }
    @PostMapping("/updateMenus")
    public CommonResult<Integer> updateMenus(@RequestBody RoleMenuUpdateParam p) {
        return CommonResult.success(roleService.updateMenus(p.getRoleId(), p.getMenuIds()));
    }
}
```

```java
@Service
public class RoleServiceImpl implements RoleService {
    @Autowired private UmsRoleMapper umsRoleMapper;
    @Autowired private UmsAdminRoleRelationMapper relationMapper;

    public List<UmsRole> list() {
        return umsRoleMapper.selectList(
            new LambdaQueryWrapper<UmsRole>().orderByAsc(UmsRole::getSort));
    }
    public Long create(UmsRoleDTO dto) {
        UmsRole r = new UmsRole();
        BeanUtils.copyProperties(dto, r);
        umsRoleMapper.insert(r);
        return r.getId();
    }
    public int update(UmsRoleDTO dto) {
        UmsRole r = new UmsRole();
        BeanUtils.copyProperties(dto, r);
        return umsRoleMapper.updateById(r);
    }
    public int delete(Long id) {
        // 删角色前先清 admin-role 关联，避免脏数据
        relationMapper.delete(new LambdaQueryWrapper<UmsAdminRoleRelation>()
            .eq(UmsAdminRoleRelation::getRoleId, id));
        return umsRoleMapper.deleteById(id);
    }
    public int updateMenus(Long roleId, List<String> menuIds) {
        UmsRole r = new UmsRole();
        r.setId(roleId);
        r.setMenuIds(menuIds == null ? null : String.join(",", menuIds));
        return umsRoleMapper.updateById(r);
    }
}
```

> `UmsRoleDTO`（前端传 name/code/description/status/sort，不含 menuIds）：从 `types/admin.ts` 的 `UmsRoleDTO` 对齐即可，可复用已有或新建。

---

## 9. SecurityConfig：加接口级鉴权

在现有 `authorizeHttpRequests` 里，把用户管理 + 角色管理接口限制为 `admin`：

```java
.authorizeHttpRequests(auth -> auth
    .requestMatchers("/admin/login", "/admin/info").permitAll()
    .requestMatchers("/role/**").hasRole("admin")
    .requestMatchers("/admin/list", "/admin/create", "/admin/update",
                     "/admin/delete/**", "/admin/updateStatus/**",
                     "/admin/role/**").hasRole("admin")
    .anyRequest().authenticated())
```

`hasRole("admin")` 会自动匹配 authorities 里的 `ROLE_admin`（与 `JwtAuthenticationTokenFilter` 注入的 `ROLE_` 前缀一致）。product 账号直接调 `/role/list` → **403** ✅

---

## 10. 编译

```powershell
mvn.cmd -o -f mall-v2/pom.xml -pl mall-admin -am compile
```

（sandbox 联网不稳加 `-o` offline；必须 `-am` 重编 mbg，否则用 .m2 陈旧 jar 报"找不到符号"）

---

## 11. 验收清单

1. admin 登录 → 系统管理可见「用户管理 / 角色管理」；product 账号登录 → **看不到** System（System 的 menuIds 不在 product 并集里，且 `meta.roles=['admin']`）。
2. 后台新建管理员、分配 product 角色 → 该账号登录后只剩 product 菜单（Dashboard/Brand/Category/Product/Order/Coupon）。
3. 后台编辑某角色、勾选/取消菜单 → 保存后该角色菜单实时变化（前端重新登录 / 刷新 info 后生效）。
4. product 账号 `curl -X POST .../role/list`（带 product token）→ **403**。
5. 编译通过。

---

## 12. 必看注意点

- **menuIds 拼写一致性**：后端 `info` 返回的 menuIds 是前端路由 `name`（Dashboard/Brand/Category/Product/Order/Coupon/System），必须与 `mall-admin-v2/src/router/index.ts` 各路由 `name` 大小写 / 拼写完全一致，否则前端过滤对不上。
- **并集去重**：多角色用户取所有角色 `menu_ids` 的 split 并集（`LinkedHashSet` 保序去重）。
- **物理删防护**：`ums_admin` 无逻辑删列，删除是真删；务必防误删 admin 账号（拒绝 `username=admin`）。
- **删角色清关联**：删 `UmsRole` 前先删 `ums_admin_role_relation` 中 `role_id=该 id` 的记录，避免脏关联。
- **CommonPage 结构**：`/admin/list` 返回 `data = {list, total}`（CommonPage），与前端 `PageResult<T>` 对齐。
- **updateStatus 参数位置**：前端发 `body {status}`，后端用 `@RequestBody` 接（或改 query，二选一对齐）。
- **前端小补（可选，AI 可直改）**：`types/admin.ts` 的 `UmsRole` 类型可加 `menuIds?: string[]`，以便角色管理页回显已选菜单。当前缺失不影响后端，但角色页回显需它。

---

## 13. 排错

- **登录后菜单没变** → 清前端 localStorage / 重新登录（前端 info 在登录时拉一次，menuIds 变更需重新 login）。
- **product 仍看到 System** → 查 `ums_role` 表 product 的 `menu_ids` 是否真不含 System（DDL 已预置）；或 `info` 的 menuIds 并集逻辑是否漏了 split。
- **403 没出现** → 检查 `SecurityConfig` 是否重新编译部署、authorities 是否含 `ROLE_admin`（`JwtAuthenticationTokenFilter` 第 48–51 行）。
