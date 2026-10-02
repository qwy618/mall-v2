<template>
  <div class="auth">
    <div class="auth__card">
      <div class="auth__brand">
        <span class="auth__logo">M</span>
        <span class="auth__title">商城</span>
      </div>
      <h2 class="auth__heading">注册账号</h2>
      <p class="auth__sub">创建账号，开启你的购物之旅</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="handleRegister"
      >
        <el-form-item label="手机号" prop="phone">
          <el-input
            v-model="form.phone"
            placeholder="请输入手机号"
            :prefix-icon="Iphone"
            size="large"
          />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input
            v-model="form.nickname"
            placeholder="昵称（选填）"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="请设置密码（至少 6 位）"
            :prefix-icon="Lock"
            size="large"
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input
            v-model="form.confirm"
            type="password"
            show-password
            placeholder="请再次输入密码"
            :prefix-icon="Lock"
            size="large"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="auth__btn"
          @click="handleRegister"
        >注册</el-button>
      </el-form>

      <div class="auth__foot">
        已有账号？<router-link to="/login" class="auth__link">去登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Iphone, Lock, User } from '@element-plus/icons-vue'
import { register } from '@/apis/member'

const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({ phone: '', nickname: '', password: '', confirm: '' })

const rules: FormRules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' },
  ],
  password: [{ required: true, min: 6, message: '密码至少 6 位', trigger: 'blur' }],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, cb) => {
        if (value !== form.password) cb(new Error('两次输入的密码不一致'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

async function handleRegister() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await register(form.phone, form.password, form.nickname || undefined)
      ElMessage.success('注册成功，请登录')
      router.push('/login')
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.auth {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--mall-primary-soft);
  padding: 24px;
}

.auth__card {
  width: 400px;
  background: var(--mall-card);
  border-radius: var(--mall-radius-lg);
  box-shadow: var(--mall-shadow);
  padding: 36px 36px 28px;
}

.auth__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.auth__logo {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--mall-primary-gradient);
  color: #fff;
  font-weight: 800;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 10px rgba(192, 116, 79, 0.3);
}

.auth__title {
  font-size: 22px;
  font-weight: 800;
  color: var(--mall-primary);
  letter-spacing: 1px;
}

.auth__heading {
  margin: 0 0 6px;
  font-size: 22px;
  color: var(--mall-text);
}

.auth__sub {
  margin: 0 0 22px;
  color: var(--mall-text-light);
  font-size: 13px;
}

.auth__btn {
  width: 100%;
  margin-top: 6px;
  background: var(--mall-primary-gradient);
  border: none;
  font-weight: 600;
  height: 44px;
}

.auth__foot {
  text-align: center;
  margin-top: 18px;
  color: var(--mall-text-light);
  font-size: 13px;
}

.auth__link {
  color: var(--mall-primary);
  font-weight: 600;
}
</style>
