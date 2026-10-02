import axios, { type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import router from '@/router'

// 1. 创建 axios 实例
const service = axios.create({
  baseURL: import.meta.env.VITE_BASE_API, // 来自 .env.development 的 VITE_BASE_API=/api
  timeout: 10000,
})

// 2. 请求拦截器：发送前统一加 token
service.interceptors.request.use(
  (config) => {
    // 优先从 Pinia user store 取 token（已随登录持久化到 localStorage）
    try {
      const token = useUserStore().userInfo.token
      if (token) {
        config.headers.set('Authorization', token)
      }
    } catch {
      // store 尚未激活时的兜底：直接读 localStorage
      const token = localStorage.getItem('token')
      if (token) {
        config.headers.set('Authorization', token)
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 3. 响应拦截器：统一处理业务码
service.interceptors.response.use(
  (response) => {
    const res = response.data
    // 后端 HTTP 恒为 200，成败看业务码
    if (res.code === 200) {
      return res.data // 只把业务数据本身往上抛
    }
    // 业务失败：弹提示并中断（401 由下方 error 分支统一处理）
    ElMessage.error(res.message || '请求失败')
    return Promise.reject(new Error(res.message || '请求失败'))
  },
  (error) => {
    // 真正的 HTTP 层错误（401 登录过期 / 超时 / 断网等）
    const status = error.response?.status
    const bodyCode = error.response?.data?.code
    // token 过期 / 未登录：后端返回 HTTP 401，axios 会进这里（不会进上面成功回调）
    if (status === 401 || bodyCode === 401) {
      const userStore = useUserStore()
      userStore.userLogout() // 清掉本地 token 状态
      const currentPath = router.currentRoute.value.path
      // 避免在登录页反复跳转 / 重复弹窗
      if (currentPath !== '/login') {
        ElMessage.error('登录已过期，请重新登录')
        router.replace({ path: '/login', query: { redirect: currentPath } })
      }
      return Promise.reject(error)
    }
    ElMessage.error(error.response?.data?.message || error.message || '网络错误')
    return Promise.reject(error)
  }
)

// 4. 泛型封装：把拦截器 return 的 res.data 透传为 T
//    axios.request<T, R> 的第二个泛型 R 才是最终 resolve 的类型
function request<T = unknown>(config: AxiosRequestConfig): Promise<T> {
  // 拦截器已把 res.data 作为结果返回，这里用断言把类型透传成 T
  return service(config) as unknown as Promise<T>
}

export default request // 对外导出泛型函数，而不是裸 service