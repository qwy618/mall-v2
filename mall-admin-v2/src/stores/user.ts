import { defineStore } from 'pinia'
import { ref } from 'vue'
import { adminLoginAPI, getAdminInfoAPI } from '@/apis/admin'
import type { AdminLoginParam } from '@/types/admin'

/**
 * 用户状态（阶段4 已接通后端）。
 *
 * persist: true 依赖 main.ts 注册的 pinia-plugin-persistedstate，
 * 默认把状态序列化到 localStorage（key = 'user'），刷新页面 token 不丢。
 */
export const useUserStore = defineStore(
  'user',
  () => {
    // 用户信息（token 是 JWT 完整串：tokenHead + token）
    const userInfo = ref<{
      username: string
      avatar: string
      roles: string[]
      token: string
      menus: string[]
    }>({
      username: '',
      avatar: '',
      roles: [],
      token: '',
      menus: [],
    })

    // 用户信息是否已从后端拉取过（刷新/持久化恢复后用于判断是否需重新拉取）
    const initialized = ref(false)

    // 写入 token（登录成功后调用）
    const setToken = (token: string) => {
      userInfo.value.token = token
    }
    // 读取 token（请求拦截器用）
    const getToken = () => userInfo.value.token

    // 登录：调 adminLoginAPI 拿 tokenHead+token，拼接后 setToken，再拉用户信息
    const userLogin = async (loginParam: AdminLoginParam) => {
      const res = await adminLoginAPI(loginParam)
      setToken(res.tokenHead + res.token)
      await getUserInfo()
    }

    // 拉取用户信息：填充 username / avatar；roles / menus 待 RBAC 阶段再补
    const getUserInfo = async () => {
      const res = await getAdminInfoAPI()
      userInfo.value.username = res.username
      userInfo.value.avatar = res.icon
      // RBAC：后端返回 roles（角色 code）+ menuIds（角色可见菜单并集）
      userInfo.value.roles = res.roles ?? []
      userInfo.value.menus = res.menuIds ?? []
      initialized.value = true
    }

    // 退出登录：清掉本地状态（persist 会自动同步到 localStorage）
    const userLogout = () => {
      userInfo.value.token = ''
      userInfo.value.username = ''
      userInfo.value.avatar = ''
      userInfo.value.roles = []
      userInfo.value.menus = []
      initialized.value = false
    }

    return { userInfo, initialized, setToken, getToken, userLogin, getUserInfo, userLogout }
  },
  {
    // 持久化配置（token 刷新不丢失）
    persist: true,
  },
)
