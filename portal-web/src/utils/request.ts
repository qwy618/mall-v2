import axios, { type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { useUserStore } from '@/stores/user'

const service = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 请求拦截：自动带上登录信息（后端 Authorization: Bearer <token>）
service.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.set('Authorization', 'Bearer ' + token)
  }
  return config
})

// 登录失效处理：清本地登录信息，避免状态错乱。
// 游客（本就未登录）的正常鉴权失败：不打扰、不弹窗、不提示；
// 仅当本次请求前确实已登录（会话失效）时，用轻提示引导重新登录。
function handleUnauthorized() {
  const userStore = useUserStore()
  const hadLoggedIn = !!userStore.token
  userStore.logout()
  if (!hadLoggedIn) return
  if (router.currentRoute.value.path === '/login') return
  ElMessage.warning('登录已失效，请重新登录')
}

// 响应拦截：解包 CommonResult -> 返回 res.data（业务数据）
// 约定后端返回 { code, message, data }，code=200 为成功
service.interceptors.response.use(
  (response) => {
    const res = response.data
    // 兜底：若后端以后改为 HTTP 200 + code=401 包装，这里也能拦截
    if (res.code === 401) {
      handleUnauthorized()
      return Promise.reject(new Error(res.message || 'Unauthorized'))
    }
    if (res.code !== 200) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || 'Error'))
    }
    return res.data
  },
  (error) => {
    const status = error.response?.status
    const data = error.response?.data
    // HTTP 401 或业务 code=401：未登录 / 会话失效
    if (status === 401 || data?.code === 401) {
      handleUnauthorized()
      return Promise.reject(error)
    }
    const msg = data?.message || error.message || '网络错误'
    ElMessage.error(msg)
    return Promise.reject(error)
  },
)

// 类型安全的请求封装：响应拦截器已解包 CommonResult，故返回业务数据 T
export default function request<T = unknown>(config: AxiosRequestConfig): Promise<T> {
  return service(config) as unknown as Promise<T>
}
