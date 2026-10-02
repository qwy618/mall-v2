# 后端接口级鉴权（RBAC 收尾）设计指南

> 目标：让后端用**和前端同一套菜单名（menuIds）**做接口级拦截。
> 现状缺口：前端隐藏 ≠ 后端禁止。`SecurityConfig` 目前只拦截 `/role/**` 和"管理员管理"那几个接口
> （`hasRole("admin")`），其余业务接口（`/brand`、`/product`、`/order`、`/coupon`、`/category`、`/sku`、`/admin/dashboard`）
> 只要求 `authenticated()`。所以 laoliu 拿 JWT 用 Postman 直调 `GET /brand/list`，**后端现在仍会放行**。
> 本方案补齐这个口子，使"前端看不到的菜单，对应接口后端也禁止"。

---

## 一、URL → 菜单名 映射表（核心约定）

后端的 URL 路径和前端的路由 `name` 不是直接相等，需要一个映射。
菜单名必须与 `mall-admin-v2/src/router/index.ts` 的路由 `name` 拼写**完全一致**
（Dashboard / Brand / Category / Product / Order / Coupon / System）。

| URL 模式（Ant）        | 菜单名    | 说明 |
|------------------------|-----------|------|
| `/brand/**`            | `Brand`   | 品牌管理 |
| `/category/**`         | `Category`| 分类管理 |
| `/coupon/**`           | `Coupon`  | 优惠券 |
| `/couponHistory/**`    | `Coupon`  | 优惠券领取记录，归入 Coupon 菜单（前缀不同，需单列） |
| `/order/**`            | `Order`   | 订单管理 |
| `/product/**`          | `Product` | 商品管理 |
| `/sku/**`              | `Product` | SKU 管理，归入 Product 菜单 |
| `/admin/dashboard/**`  | `Dashboard`| 看板（注意：只能用 `/admin/dashboard/**`，不能用 `/admin/**`，否则误伤 login/info） |

**以下不进映射表（拦截器一律放行，交给 `SecurityConfig` 或匿名放行）：**
- `/role/**`、 `/admin/list`、`/admin/create`、`/admin/update`、`/admin/delete/**`、`/admin/updateStatus/**`、`/admin/role/**`
  → 已被 `SecurityConfig.hasRole("admin")` 覆盖，无需映射。
- `/admin/login`、`/admin/info` → 任何登录用户都要调，不能按菜单拦。
- `/oss/**` → 图片上传，暂放行（如需收紧可归入 `Product`）。
- 静态资源、`/error`、swagger 等。

---

## 二、改动清单（4 个文件，全在 `mall-admin` 模块）

| # | 文件 | 动作 | 作用 |
|---|------|------|------|
| 1 | `component/AdminUserDetails.java` | 改 | 增加 `menuIds` 字段 + getter + 构造器参数 |
| 2 | `service/Impl/UserDetailsServiceImpl.java` | 改 | 登录时计算 `menuIds` 并集并注入 `AdminUserDetails` |
| 3 | `component/MenuPermissionInterceptor.java` | **新建** | 统一授权拦截器：URL→菜单名 比对，admin 短路，无权限写 JSON 403 |
| 4 | `config/WebMvcConfig.java` | **新建** | 注册拦截器并排除 login/info/静态资源 |

> `SecurityConfig` **不用动**（保留 `hasRole("admin")` 那几行）。

---

## 三、关键代码

### 1) AdminUserDetails —— 加 menuIds

```java
public class AdminUserDetails implements UserDetails {
    private UmsAdmin umsAdmin;
    private List<UmsRole> roles;
    private List<String> menuIds;          // ← 新增

    public AdminUserDetails(UmsAdmin umsAdmin, List<UmsRole> roles, List<String> menuIds) {
        this.umsAdmin = umsAdmin;
        this.roles = roles;
        this.menuIds = menuIds != null ? menuIds : Collections.emptyList();
    }

    // 已有 getRoles() 保留
    public List<String> getMenuIds() {     // ← 新增
        return menuIds;
    }
    // ... 其余不变 ...
}
```

### 2) UserDetailsServiceImpl —— 登录时算 menuIds 并集

逻辑与 `AdminServiceImpl.info()` 里的并集算法**完全一致**（可复制那段）。

```java
@Override
public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
    UmsAdmin umsAdmin = umsAdminMapper.selectOne(
            new LambdaQueryWrapper<UmsAdmin>().eq(UmsAdmin::getUsername, username));
    if (umsAdmin == null) throw new UsernameNotFoundException("User not found");

    List<UmsAdminRoleRelation> relations = umsAdminRoleRelationMapper.selectList(
            new LambdaQueryWrapper<UmsAdminRoleRelation>().eq(UmsAdminRoleRelation::getAdminId, umsAdmin.getId()));
    List<UmsRole> roles = relations.stream()
            .map(r -> umsRoleMapper.selectById(r.getRoleId()))
            .filter(Objects::nonNull)
            .collect(Collectors.toList());

    // ↓↓↓ 新增：所有角色的 menu_ids 逗号 split 后并集去重 ↓↓↓
    Set<String> menuSet = new LinkedHashSet<>();
    roles.forEach(r -> {
        if (r.getMenuIds() != null && !r.getMenuIds().isBlank()) {
            for (String s : r.getMenuIds().split(",")) {
                String t = s.trim();
                if (!t.isEmpty()) menuSet.add(t);
            }
        }
    });
    List<String> menuIds = new ArrayList<>(menuSet);

    return new AdminUserDetails(umsAdmin, roles, menuIds);   // ← 三参构造
}
```

> ⚠️ 必须先给 `UmsRole` 实体补 `menuIds` 字段（RBAC 阶段已做：重跑 MBG 或手写 `private String menuIds;` + getter/setter）。
> 若 `UmsRole.getMenuIds()` 不存在，上面会编译报错。

### 3) MenuPermissionInterceptor —— 新建（核心）

```java
package com.macro.mall.admin.component;

import com.macro.mall.admin.component.AdminUserDetails;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.servlet.HandlerInterceptor;
import java.util.LinkedHashMap;
import java.util.Map;

public class MenuPermissionInterceptor implements HandlerInterceptor {

    private static final AntPathMatcher MATCHER = new AntPathMatcher();
    // URL 模式 → 菜单名（与前端 router name 一致）
    private static final Map<String, String> MENU_MAP = new LinkedHashMap<>() {{
        put("/brand/**", "Brand");
        put("/category/**", "Category");
        put("/coupon/**", "Coupon");
        put("/couponHistory/**", "Coupon");
        put("/order/**", "Order");
        put("/product/**", "Product");
        put("/sku/**", "Product");
        put("/admin/dashboard/**", "Dashboard");
    }};

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        // 未认证：交给 SecurityConfig 处理 401（正常到不了这里，因为已 authenticated()）
        if (auth == null || !auth.isAuthenticated()) return true;

        Object principal = auth.getPrincipal();
        if (!(principal instanceof AdminUserDetails details)) return true;

        // ① admin 短路：超级管理员放行一切
        boolean isAdmin = details.getUsername().equals("admin")
                || auth.getAuthorities().stream().anyMatch(a -> "ROLE_admin".equals(a.getAuthority()));
        if (isAdmin) return true;

        // ② 当前 URL 需要的菜单名
        String requiredMenu = matchMenu(request.getRequestURI());
        if (requiredMenu == null) return true;   // 不在映射里（login/info/oss/静态）→ 放行

        // ③ 用户的 menuIds 是否包含该菜单名
        if (details.getMenuIds().contains(requiredMenu)) return true;

        // ④ 无权限：写 JSON 403 并中断
        response.setStatus(HttpServletResponse.SC_FORBIDDEN);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"code\":403,\"message\":\"无权限访问该接口\"}");
        return false;
    }

    private String matchMenu(String uri) {
        for (Map.Entry<String, String> e : MENU_MAP.entrySet()) {
            if (MATCHER.match(e.getKey(), uri)) return e.getValue();
        }
        return null;
    }
}
```

> 注意：`jakarta.servlet`（Spring Boot 3）包名，别 import 成 `javax.servlet`。

### 4) WebMvcConfig —— 新建，注册拦截器

```java
package com.macro.mall.admin.config;

import com.macro.mall.admin.component.MenuPermissionInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    private final MenuPermissionInterceptor menuPermissionInterceptor;
    public WebMvcConfig(MenuPermissionInterceptor menuPermissionInterceptor) {
        this.menuPermissionInterceptor = menuPermissionInterceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(menuPermissionInterceptor)
                .addPathPatterns("/**")
                .excludePathPatterns(
                        "/admin/login", "/admin/info",          // 任何人都要调
                        "/error",
                        "/**/*.css", "/**/*.js", "/**/*.png",
                        "/**/*.jpg", "/**/*.ico", "/favicon.ico",
                        "/swagger-ui/**", "/v3/api-docs/**", "/doc.html"  // 若启了 swagger
                );
    }
}
```

> `MenuPermissionInterceptor` 用 `@Component` 标注（或在此 `@Bean`），保证能被注入。

---

## 四、编译 & 验收

**编译（沿用红线已知可用命令）：**
```powershell
$mvn = "C:\Users\29154\.m2\wrapper\dists\apache-maven-3.9.11-bin\6mqf5t809d9geo83kj4ttckcbc\apache-maven-3.9.11\bin\mvn.cmd"
& $mvn -o -f "C:\Users\29154\Desktop\全栈项目\mall-v2\pom.xml" -pl mall-admin -am compile -DskipTests
```
期望 `BUILD SUCCESS`。

**验收（用 Postman 带 JWT 直调，验证"隐藏=禁止"）：**
1. **admin** 登录 → 所有接口正常（短路放行）。
2. **product** 角色账号 → `GET /brand/list`、`/order/list`、`/coupon/list` 应返 **403 JSON**；
   `GET /category/list`、`/product/list`、`/sku/list` 正常；`GET /admin/info` 正常。
3. **youhui** 角色账号 → `GET /brand/list`、`/category/list`、`/product/list` 返 403；
   `GET /order/list`、`/coupon/list`、`/admin/dashboard/**` 正常。
4. 前端无感：菜单本来就不显示无权限项，现在后端也真拦了，体验一致。

**前端小优化（可选，AI 直写范围）：**
`mall-admin-v2/src/utils/request.ts` 的 error 回调里，对 `status === 403` 加一句
`ElMessage.error(error.response?.data?.message || '无权限访问')`，让越权操作有提示。

---

## 五、排错清单（易踩点）

- **所有非 admin 都 403？** 99% 是 `menuIds` 没注入 `AdminUserDetails`
  （只在 `info()` 算、没在 `UserDetailsServiceImpl` 注入）。拦截器拿到的就是空集合。
- **登录后前端崩 / info 被拦？** 检查映射表是否误用 `/admin/**`（会连 `/admin/info` 一起拦）。必须用 `/admin/dashboard/**`。
- **`principal` 强转报错？** 确认 `UserDetailsServiceImpl` 返回的就是 `AdminUserDetails`（本仓库是）。
- **拦截器不生效？** 确认 `WebMvcConfig` 被扫到（`@Configuration` 在 `com.macro.mall.admin` 包下）且 `MenuPermissionInterceptor` 是 Spring Bean。
- **包名错误？** Spring Boot 3 用 `jakarta.servlet`，不是 `javax.servlet`。
- **两层不冲突：** HandlerInterceptor 在 Security 过滤器链（含 `authorizeHttpRequests`）之后、DispatcherServlet 之内执行；
  `SecurityConfig` 先认证+粗粒度授权，`MenuPermissionInterceptor` 做细粒度菜单授权，互不干扰。
```
