<template>
  <el-dialog
    v-model="gate.visible"
    width="380px"
    align-center
    :show-close="false"
    class="login-gate"
    append-to-body
  >
    <div class="lg">
      <div class="lg__icon">
        <el-icon :size="28"><Lock /></el-icon>
      </div>
      <h3 class="lg__title">{{ gate.title || '登录后即可继续' }}</h3>
      <p class="lg__desc">
        {{ gate.message || '登录后可查看该页面，还能同步购物车、订单与会员权益' }}
      </p>
      <div class="lg__actions">
        <button type="button" class="lg__btn lg__btn--ghost" @click="gate.close()">稍后再说</button>
        <button type="button" class="lg__btn lg__btn--primary" @click="goLogin">去登录</button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Lock } from '@element-plus/icons-vue'
import { useLoginGate } from '@/stores/loginGate'

const router = useRouter()
const gate = useLoginGate()

function goLogin() {
  const target = gate.redirect
  gate.close()
  router.push({ path: '/login', query: target ? { redirect: target } : {} })
}
</script>

<!-- 弹窗被 teleport 到 body，需用非 scoped 全局样式才能命中 .el-dialog -->
<style>
.el-dialog.login-gate {
  padding: 0;
  border-radius: 16px;
  overflow: hidden;
  background: var(--mall-card);
  box-shadow: 0 16px 44px rgba(120, 84, 60, 0.22);
}
.login-gate .el-dialog__header {
  display: none;
}
.login-gate .el-dialog__body {
  padding: 30px 30px 26px;
}

.lg {
  text-align: center;
}
.lg__icon {
  width: 62px;
  height: 62px;
  margin: 0 auto 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: var(--mall-primary-gradient);
  box-shadow: 0 6px 16px rgba(192, 116, 79, 0.32);
}
.lg__title {
  margin: 0 0 8px;
  font-family: var(--mall-font-serif);
  font-size: 20px;
  font-weight: 700;
  color: var(--mall-text);
  letter-spacing: 0.5px;
}
.lg__desc {
  margin: 0 0 22px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--mall-text-light);
}
.lg__actions {
  display: flex;
  gap: 12px;
}
.lg__btn {
  flex: 1;
  height: 42px;
  border-radius: var(--mall-radius);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: color 0.18s ease, border-color 0.18s ease, background 0.18s ease,
    filter 0.18s ease;
}
.lg__btn--ghost {
  background: #fff;
  color: var(--mall-text-regular);
  border-color: var(--mall-border);
}
.lg__btn--ghost:hover {
  color: var(--mall-primary);
  border-color: var(--mall-primary-light);
  background: var(--mall-primary-soft);
}
.lg__btn--primary {
  background: var(--mall-primary-gradient);
  color: #fff;
  box-shadow: 0 6px 14px rgba(192, 116, 79, 0.3);
}
.lg__btn--primary:hover {
  filter: brightness(1.05);
}
</style>
