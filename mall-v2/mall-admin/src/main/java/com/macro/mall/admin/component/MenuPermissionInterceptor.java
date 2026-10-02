package com.macro.mall.admin.component;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.AntPathMatcher;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 接口级菜单鉴权拦截器。
 *
 * 与前端 mall-admin-v2 用同一套菜单名（route name）做判断：
 * 前端菜单隐藏 ≡ 后端对应接口拦截，做到「前端看不到 = 后端禁止」。
 * 该拦截器在 Security 过滤器链（含 authorizeHttpRequests）之后、DispatcherServlet 之内执行，
 * 与 SecurityConfig 的 hasRole("admin") 粗粒度授权互不冲突。
 */
@Component
public class MenuPermissionInterceptor implements HandlerInterceptor {

    private static final AntPathMatcher MATCHER = new AntPathMatcher();

    // URL 模式 → 菜单名（必须与前端 src/router/index.ts 的路由 name 完全一致）
    private static final Map<String, String> MENU_MAP = new LinkedHashMap<>() {{
        put("/brand/**", "Brand");
        put("/category/**", "Category");
        put("/coupon/**", "Coupon");
        put("/couponHistory/**", "Coupon");
        put("/order/**", "Order");
        put("/product/**", "Product");
        put("/sku/**", "Product");
        put("/comment/**", "Comment");
        put("/admin/dashboard/**", "Dashboard");
    }};

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        // 未认证：正常到不了这里（SecurityConfig 已是 authenticated()），交给 Security 处理
        if (auth == null || !auth.isAuthenticated()) {
            return true;
        }

        Object principal = auth.getPrincipal();
        if (!(principal instanceof AdminUserDetails details)) {
            return true;
        }

        // ① admin 短路：超级管理员放行一切
        boolean isAdmin = "admin".equals(details.getUsername())
                || auth.getAuthorities().stream().anyMatch(a -> "ROLE_admin".equals(a.getAuthority()));
        if (isAdmin) {
            return true;
        }

        // ② 当前请求需要的菜单名
        String requiredMenu = matchMenu(request.getRequestURI());
        if (requiredMenu == null) {
            return true; // 不在映射表（login/info/oss/静态资源等）→ 放行
        }

        // ③ 用户 menuIds 是否包含该菜单名
        if (details.getMenuIds().contains(requiredMenu)) {
            return true;
        }

        // ④ 无权限：写 JSON 403 并中断
        response.setStatus(HttpServletResponse.SC_FORBIDDEN);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"code\":403,\"message\":\"无权限访问该接口\"}");
        return false;
    }

    private String matchMenu(String uri) {
        for (Map.Entry<String, String> entry : MENU_MAP.entrySet()) {
            if (MATCHER.match(entry.getKey(), uri)) {
                return entry.getValue();
            }
        }
        return null;
    }
}
