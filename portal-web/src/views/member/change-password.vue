<template>
  <div class="cp">
    <div class="cp__card">
      <h2 class="cp__title">修改密码</h2>
      <p class="cp__sub">为保障账户安全，修改密码需验证原密码</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="handleSubmit"
      >
        <el-form-item label="原密码" prop="oldPassword">
          <el-input
            v-model="form.oldPassword"
            type="password"
            show-password
            placeholder="请输入当前密码"
            :prefix-icon="Lock"
            size="large"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="form.newPassword"
            type="password"
            show-password
            placeholder="6-20 位，区分大小写"
            :prefix-icon="Key"
            size="large"
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入新密码"
            :prefix-icon="Check"
            size="large"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="cp__btn"
          @click="handleSubmit"
        >确认修改</el-button>
        <el-button size="large" class="cp__btn" @click="goBack">取消</el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Lock, Key, Check } from '@element-plus/icons-vue'
import { updatePassword } from '@/apis/member'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const validateConfirm = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (value !== form.newPassword) {
    callback(new Error('两次输入的新密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度需为 6-20 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await updatePassword(form.oldPassword, form.newPassword)
      ElMessage.success('密码修改成功，请重新登录')
      userStore.logout()
      router.replace('/login')
    } catch {
      // 错误提示已由拦截器统一弹出（如「原密码错误」）
    } finally {
      loading.value = false
    }
  })
}

function goBack() {
  router.back()
}
</script>

<style scoped>
.cp {
  max-width: 460px;
  margin: 0 auto;
  padding: 40px 16px 48px;
}
.cp__card {
  background: var(--mall-card);
  border-radius: var(--mall-radius-lg);
  padding: 32px 32px 28px;
  box-shadow: var(--mall-shadow);
}
.cp__title {
  margin: 0 0 6px;
  font-size: 22px;
  font-family: var(--mall-font-serif);
  color: var(--mall-text);
}
.cp__sub {
  margin: 0 0 22px;
  font-size: 13px;
  color: var(--mall-text-light);
}
.cp__btn {
  width: 100%;
  margin-top: 6px;
  margin-left: 0;
  font-weight: 600;
}
.cp__btn + .cp__btn {
  margin-top: 12px;
}
</style>
