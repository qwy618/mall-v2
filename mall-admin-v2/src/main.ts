import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './styles/index.css'

import App from './App.vue'
import router from './router'
import '@/router/guard' // 注册路由前置/后置守卫（NProgress + token 校验）

const app = createApp(App)
const pinia = createPinia()
// 启用 Pinia 状态持久化（user store 的 token 刷新不丢失）
pinia.use(piniaPluginPersistedstate)

app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')
