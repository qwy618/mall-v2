import 'vue-router'

/**
 * 扩展 vue-router 的 RouteMeta，加入 RBAC 菜单需要的字段。
 * 放在独立文件并被任意模块 import 后，全局 RouteMeta 即获得这些可选字段。
 */
declare module 'vue-router' {
  interface RouteMeta {
    /** 菜单/页面标题，layout 标题栏会读取 */
    title?: string
    /** 菜单图标名，对应 @element-plus/icons-vue 的导出名，如 'DataLine' */
    icon?: string
    /**
     * 允许访问该菜单的角色 code 列表（对齐后端 ums_role.code）：
     *   - 不填 / 空数组 = 所有已登录用户可见
     *   - 填了 = 仅列出的角色可见
     * 注意：超级管理员角色 'admin' 始终可见（见 utils/permission 的 canAccess）
     */
    roles?: string[]
    /** 是否在侧边栏菜单中隐藏（登录页等用），默认 false */
    hidden?: boolean
  }
}
