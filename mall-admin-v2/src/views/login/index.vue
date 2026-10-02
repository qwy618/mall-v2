<template>
  <div class="login">
    <div class="login__banner">
      <div class="login__brand">
        <span class="login__logo">商</span>
        <span class="login__brand-name">Mall 管理后台</span>
      </div>
      <h1 class="login__slogan">电商后台<br />一站式管理</h1>
      <ul class="login__features">
        <li><el-icon><Goods /></el-icon> 商品 / 库存管理</li>
        <li><el-icon><Tickets /></el-icon> 订单全流程跟踪</li>
        <li><el-icon><DataLine /></el-icon> 经营数据看板</li>
        <li><el-icon><Discount /></el-icon> 营销优惠券</li>
      </ul>
    </div>

    <div class="login__panel">
      <div class="login__card">
        <h2 class="login__title">账号登录</h2>
        <p class="login__desc">欢迎回来，请登录您的管理账号</p>

        <el-form
          ref="formRef"
          :model="loginForm"
          :rules="rules"
          label-position="top"
          @keyup.enter="handleLogin"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              :prefix-icon="User"
              size="large"
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              show-password
              placeholder="请输入密码"
              :prefix-icon="Lock"
              size="large"
            />
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="login__btn"
            @click="handleLogin"
          >登录</el-button>
        </el-form>

        <p class="login__tip">种子账号：admin / macro123</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, Goods, Tickets, DataLine, Discount } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const loginForm = reactive({
  username: 'admin',
  password: 'macro123',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const handleLogin = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await userStore.userLogin({ ...loginForm })
      ElMessage.success('登录成功')
      // 优先跳回登录前想去的页面，否则进首页
      const redirect = (route.query.redirect as string) || '/'
      router.push(redirect)
    } catch {
      // 登录/拉取用户信息失败：请求拦截器已弹出具体错误提示，这里兜底
      // 防止 unhandled rejection，并停留在登录页让用户重试
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login {
  height: 100vh;
  display: flex;
}

.login__banner {
  flex: 1;
  background:
    radial-gradient(90% 70% at 80% 0%, rgba(255, 236, 214, 0.35) 0%, rgba(255, 236, 214, 0) 60%),
    linear-gradient(150deg, #cd8560 0%, #b06a44 52%, #9a5a36 100%);
  color: #fff8f2;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 8%;
  position: relative;
  overflow: hidden;
}

.login__banner::after {
  content: '';
  position: absolute;
  right: -80px;
  top: -80px;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
}

.login__banner::before {
  content: '';
  position: absolute;
  left: -60px;
  bottom: -100px;
  width: 280px;
  height: 280px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
}

.login__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 40px;
}

.login__logo {
  width: 42px;
  height: 42px;
  border-radius: 11px;
  background: rgba(255, 248, 242, 0.22);
  border: 1px solid rgba(255, 248, 242, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--mall-font-serif);
  font-weight: 700;
  font-size: 20px;
}

.login__brand-name {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 1px;
  font-family: var(--mall-font-serif);
}

.login__slogan {
  font-size: 40px;
  font-weight: 700;
  line-height: 1.35;
  margin: 0 0 36px;
  font-family: var(--mall-font-serif);
  letter-spacing: 2px;
}

.login__features {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.login__features li {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 16px;
  opacity: 0.95;
}

.login__features .el-icon {
  font-size: 22px;
}

.login__panel {
  width: 480px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--admin-card);
}

.login__card {
  width: 340px;
}

.login__title {
  margin: 0 0 6px;
  font-size: 24px;
  color: var(--admin-text);
  font-family: var(--mall-font-serif);
  font-weight: 700;
}

.login__desc {
  margin: 0 0 28px;
  color: var(--admin-text-light);
  font-size: 13px;
}

.login__btn {
  width: 100%;
  margin-top: 8px;
  background: var(--mall-primary-gradient);
  border: none;
  font-weight: 600;
  height: 44px;
  border-radius: 10px;
  letter-spacing: 2px;
}

.login__btn:hover {
  opacity: 0.92;
}

.login__tip {
  text-align: center;
  color: var(--admin-text-light);
  font-size: 12px;
  margin: 18px 0 0;
}

@media (max-width: 900px) {
  .login__banner {
    display: none;
  }
  .login__panel {
    width: 100%;
  }
}
</style>
