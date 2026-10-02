import type { RouteRecordRaw } from 'vue-router'

/**
 * RBAC 前端菜单/路由权限工具。
 *
 * 核心约定：超级管理员角色 `admin` 始终可见全部菜单、可访问全部路由
 * （绕过 roles 过滤）。这是通用后台的惯例，也契合 mall 原版「超级管理员
 * 拥有所有权限」的语义。其余角色严格按 meta.roles 匹配。
 */

/**
 * 判断某个路由是否对当前用户可见。
 *
 * 优先级：
 *  1) 超级管理员(admin) 始终全可见（绕过任何过滤）
 *  2) 若后端下发了 menuIds（非空）= 严格按「角色可见菜单」过滤：
 *     路由的 name 必须在 menuIds 中才可见（实现真正的后台可配菜单）
 *  3) 否则回退到路由 meta.roles 的静态角色过滤（兜底 / 旧逻辑）
 *
 * @param rolesInMeta 路由 meta.roles（允许访问的角色 code 列表，可能 undefined）
 * @param userRoles   当前用户拥有的角色 code 列表（来自后端 info）
 * @param menuIds     后端返回的角色可见菜单并集（前端路由 name）；空=未启用动态菜单
 * @param routeName   当前路由的 name（如 'Dashboard'），用于动态菜单比对
 */
export function canAccess(
  rolesInMeta: string[] | undefined,
  userRoles: string[],
  menuIds: string[] = [],
  routeName?: string | symbol
): boolean {
  // 1) 超级管理员全可见
  if (userRoles.includes('admin')) return true
  // 2) 动态菜单生效：route.name 必须在 menuIds 中
  if (menuIds.length > 0) {
    return routeName != null && menuIds.includes(String(routeName))
  }
  // 3) 回退：静态 meta.roles 过滤
  if (!rolesInMeta || rolesInMeta.length === 0) return true
  return rolesInMeta.some((r) => userRoles.includes(r))
}

/**
 * 从一组路由中过滤出当前用户可访问的菜单项。
 * 通常用于布局 '/' 下的 children 数组。
 */
export function filterMenuRoutes(
  routes: RouteRecordRaw[],
  userRoles: string[],
  menuIds: string[] = []
): RouteRecordRaw[] {
  return routes.filter((r) =>
    canAccess(r.meta?.roles, userRoles, menuIds, r.name)
  )
}
