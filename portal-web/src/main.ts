import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import './styles/global.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
// 注入中文语言包：消除组件内置英文（如分页器的 "Total 38"、空态的 "No Data" 等）
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
