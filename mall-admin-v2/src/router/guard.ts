import router from '@/router'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { useUserStore } from '@/stores/user'
import { canAccess } from '@/utils/permission'

// 关闭右侧旋转小圈，只保留顶部进度条
NProgress.configure({ showSpinner: false })

// 免登录白名单（登录页本身不需要鉴权）
const whiteList = ['/login']

// 路由前置守卫：每次跳转都会执行
router.beforeEach(async (to, _from, next) => {
  NProgress.start()
  const userStore = useUserStore()
  if (userStore.userInfo.token) {
    // 已登录：确保用户信息（含 roles）已从后端加载。
    // 解决 persist 旧缓存 / 刷新页面后 roles 为空导致菜单只剩首页的问题。
    if (!userStore.initialized || userStore.userInfo.roles.length === 0) {
      try {
        await userStore.getUserInfo()
      } catch {
        // 拉取失败（如 token 过期）：清状态回登录页
        userStore.userLogout()
        next('/login')
        NProgress.done()
        return
      }
    }
    // 已登录：想去登录页就直接进首页，否则放行
    if (to.path === '/login') {
      next('/')
    } else {
      // 已登录访问业务页：按角色判断权限（超级管理员 / 菜单 menuIds / 静态角色）
      // ⚠️ 必须与侧边栏 filterMenuRoutes 用同一套逻辑（统一传 menuIds + 路由名），
      //    否则会出现「菜单显示但点击被守卫打回首页」的不一致。
      // ⚠️ Dashboard(首页) 对所有已登录用户无条件放行：否则某角色漏配 'Dashboard' 时，
      //    登录后 push('/') → redirect '/dashboard' 被拦 → next('/') → 再 redirect
      //    → 无限重定向，表现为「登录后卡死」。
      const isHome =
        to.name === 'Dashboard' || to.path === '/' || to.path === '/dashboard'
      if (isHome || canAccess(to.meta.roles, userStore.userInfo.roles, userStore.userInfo.menus, to.name)) {
        next()
      } else {
        // 无权限：打回首页（后续可换成专门的 403 页）
        next('/')
      }
    }
  } else {
    // 未登录：在白名单里放行，否则跳登录页
    if (whiteList.includes(to.path)) {
      next()
    } else {
      next('/login')
    }
  }
})

// 路由后置守卫：结束进度条
router.afterEach(() => {
  NProgress.done()
})
