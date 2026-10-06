<template>
  <div class="auth">
    <div class="auth__card">
      <div class="auth__brand">
        <MallLogo :size="40" />
      </div>
      <h2 class="auth__heading">账号登录</h2>
      <p class="auth__sub">欢迎回来，挑选你想要的好物</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="handleLogin"
      >
        <el-form-item label="手机号" prop="phone">
          <el-input
            v-model="form.phone"
            placeholder="请输入手机号"
            :prefix-icon="Iphone"
            size="large"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
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
          class="auth__btn"
          @click="handleLogin"
        >登录</el-button>
      </el-form>

      <div class="auth__foot">
        还没有账号？<router-link to="/register" class="auth__link">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Iphone, Lock } from '@element-plus/icons-vue'
import { login } from '@/apis/member'
import { mergeGuestCart } from '@/apis/cart'
import { useUserStore } from '@/stores/user'
import MallLogo from '@/components/MallLogo.vue'
import { getGuestCart, clearGuestCart } from '@/utils/guestCart'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({ phone: '', password: '' })

const rules: FormRules = {
  phone: [{ required: true, message: '请输入手机号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const data = await login(form.phone, form.password)
      userStore.setToken(data.token)
      userStore.setNickname(data.member.nickname || data.member.phone || '')
      userStore.setPhone(data.member.phone || '')
      userStore.setIcon(data.member.icon || '')
      ElMessage.success('登录成功')
      // 未登录期间加购的暂存车：登录后合并进会员购物车并清空
      const guestItems = getGuestCart()
      const hadGuest = guestItems.length > 0
      if (hadGuest) {
        try {
          // 合并只传后端所需字段（skuId + 数量），避免多余快照字段被判为非法入参
          await mergeGuestCart(guestItems.map((i) => ({ skuId: i.skuId, quantity: i.quantity })))
        } catch {
          // 合并失败不阻断登录；暂存车保留，下次登录重试
        }
        clearGuestCart()
      }
      // 登录后回跳：优先弹窗带入的 redirect，其次有暂存车去购物车，否则回首页
      const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
      router.push(redirect || (hadGuest ? '/cart' : '/product'))
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
  background: #fff;
  border-radius: var(--mall-radius-lg);
  box-shadow: var(--mall-shadow);
  padding: 36px 36px 28px;
}

.auth__brand {
  display: flex;
  align-items: center;
  margin-bottom: 18px;
}

.auth__heading {
  margin: 0 0 6px;
  font-size: 22px;
  font-family: var(--mall-font-serif);
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
