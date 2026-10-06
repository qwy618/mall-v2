<template>
  <div class="app">
    <!-- 顶部导航（暖色生活方式风），登录/注册页隐藏 -->
    <header class="header" v-if="!route.meta.hideHeader">
      <!-- 顶部工具条 -->
      <div class="utility">
        <div class="utility__inner">
          <span class="utility__welcome">
            <template v-if="userStore.token">您好，{{ userStore.nickname || '会员' }}，欢迎回到商城</template>
            <template v-else>您好，欢迎来到商城，<router-link to="/login" style="color: var(--mall-primary)">登录</router-link>后享更多权益</template>
          </span>
          <nav class="utility__links">
            <template v-if="userStore.token">
              <router-link to="/member">个人中心</router-link>
              <router-link to="/order/list">我的订单</router-link>
              <router-link to="/coupon">我的优惠券</router-link>
              <router-link to="/cart">购物车</router-link>
              <a class="utility__logout" @click="handleLogout">退出登录</a>
            </template>
            <template v-else>
              <router-link to="/login">登录</router-link>
              <router-link to="/register">注册</router-link>
            </template>
          </nav>
        </div>
      </div>

      <!-- 主搜索行 -->
      <div class="header__main">
        <div class="header__inner">
          <router-link to="/product" class="logo">
            <MallLogo :size="36" />
          </router-link>

          <div class="search">
            <input
              v-model="keyword"
              class="search__input"
              type="text"
              placeholder="搜索商品名称 / 品牌"
              @keyup.enter="goSearch"
            />
            <button class="search__btn" type="button" @click="goSearch">
              <el-icon><Search /></el-icon>搜索
            </button>
          </div>

          <div class="header__actions">
            <button
              class="assistant-btn"
              :class="{ 'is-open': assistantOpen }"
              type="button"
              :title="assistantOpen ? '收起购物助手' : '打开购物助手'"
              @click="assistantOpen = !assistantOpen"
            >
              <AssistantBellIcon :size="16" />
              <span class="assistant-btn__text">助手</span>
            </button>

            <router-link to="/cart" class="cart-btn">
              <el-badge :value="cartCount" :max="99" :hidden="cartCount === 0">
                <span class="cart-btn__inner">
                  <el-icon :size="16"><ShoppingCart /></el-icon>购物车
                </span>
              </el-badge>
            </router-link>
          </div>
        </div>
      </div>
    </header>

    <main class="content">
      <router-view />
    </main>

    <!-- 登录引导弹窗：需登录页面/操作不再硬跳登录页，改为弹窗引导 -->
    <LoginGate />

    <!-- 智能购物助手：桌面端入口在导航栏购物车左侧，移动端为右下悬浮球（登录/注册页不出现） -->
    <AiAssistant v-if="!route.meta.hideHeader" v-model:open="assistantOpen" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, ShoppingCart } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { listCart } from '@/apis/cart'
import { guestCartCount } from '@/utils/guestCart'
import LoginGate from '@/components/LoginGate.vue'
import MallLogo from '@/components/MallLogo.vue'
import AiAssistant from '@/components/ai/AiAssistant.vue'
import AssistantBellIcon from '@/components/ai/AssistantBellIcon.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const keyword = ref('')
const cartCount = ref(0)
/** 购物助手面板展开态：导航栏按钮与面板内「收起」共用（面板移动端由悬浮球驱动） */
const assistantOpen = ref(false)

// 顶栏搜索框与路由 keyword 双向同步：
// - 在搜索结果页(/search)时，回显当前关键词；
// - 离开搜索结果页（含浏览器回退到首页/其他页）自动清空，满足「回退清空搜索」。
watch(
  () => [route.path, route.query.keyword],
  () => {
    keyword.value =
      route.path === '/search'
        ? (typeof route.query.keyword === 'string' ? route.query.keyword : '')
        : ''
    // 游客在购物车页增删改后，回到其他页时刷新角标
    if (!userStore.token) cartCount.value = guestCartCount()
  },
  { immediate: true }
)

function goSearch() {
  const kw = keyword.value.trim()
  router.push({ path: '/search', query: kw ? { keyword: kw } : {} })
}

async function loadCartCount() {
  try {
    const items = await listCart()
    cartCount.value = (items || []).reduce((sum, it) => sum + (it.quantity || 0), 0)
  } catch {
    cartCount.value = 0
  }
}

function handleLogout() {
  userStore.logout()
  // 退出登录回首页（不强制进登录页）
  router.push('/product')
}

// 购物车角标：登录读会员购物车，未登录读 localStorage 暂存车；登录态变化后刷新
watch(
  () => userStore.token,
  (t) => {
    if (t) loadCartCount()
    else cartCount.value = guestCartCount()
  },
  { immediate: true }
)
</script>

<style scoped>
.app {
  min-height: 100vh;
  background: var(--mall-bg);
}

.header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--mall-card);
}

/* ---------- 顶部工具条（暖灰底） ---------- */
.utility {
  background: #f5ede4;
  border-bottom: 1px solid var(--mall-border);
}
.utility__inner {
  max-width: 1200px;
  margin: 0 auto;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  font-size: 12px;
  color: var(--mall-text-light);
}
.utility__links {
  display: flex;
  align-items: center;
  gap: 16px;
}
.utility__links a {
  color: var(--mall-text-light);
  cursor: pointer;
}
.utility__links a:hover {
  color: var(--mall-primary);
}

/* ---------- 主搜索行 ---------- */
.header__main {
  border-bottom: 1px solid var(--mall-border);
  box-shadow: 0 1px 3px rgba(168, 130, 100, 0.04);
}
.header__inner {
  max-width: 1200px;
  margin: 0 auto;
  height: 80px;
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 0 16px;
}

.logo {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.search {
  flex: 1;
  max-width: 560px;
  height: 38px;
  display: flex;
  border: 2px solid var(--mall-primary);
  border-radius: var(--mall-radius);
  overflow: hidden;
  background: #fff;
}
.search__input {
  flex: 1;
  border: none;
  outline: none;
  padding: 0 12px;
  font-size: 14px;
  color: var(--mall-text);
}
.search__input::placeholder {
  color: #c3b6a8;
}
.search__btn {
  width: 92px;
  flex-shrink: 0;
  border: none;
  background: var(--mall-primary);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.search__btn:hover {
  background: var(--mall-primary-dark);
}

/* 顶栏右侧动作区：助手 + 购物车（整体靠右） */
.header__actions {
  flex-shrink: 0;
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.assistant-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  border: 1px solid var(--mall-primary);
  color: var(--mall-primary);
  border-radius: var(--mall-radius);
  font-size: 13px;
  background: #fff;
  cursor: pointer;
  transition: background 0.16s ease, color 0.16s ease;
}
.assistant-btn:hover {
  background: var(--mall-primary-soft);
}
/* 面板展开时转为实心：与描边购物车形成主次，也便于一眼看出助手是开着的 */
.assistant-btn.is-open {
  background: var(--mall-primary);
  border-color: var(--mall-primary);
  color: #fff;
}
/* 打开时铃以底盘为轴摆一下 —— 呼应「按铃叫人」的动作 */
.assistant-btn.is-open .assistant-bell {
  transform-origin: 50% 74%;
  animation: assist-ring 0.5s ease-in-out;
}
@keyframes assist-ring {
  0%,
  100% {
    transform: rotate(0);
  }
  30% {
    transform: rotate(-9deg);
  }
  70% {
    transform: rotate(9deg);
  }
}

.cart-btn {
  flex-shrink: 0;
}
.cart-btn__inner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 16px;
  border: 1px solid var(--mall-primary);
  color: var(--mall-primary);
  border-radius: var(--mall-radius);
  font-size: 13px;
  background: #fff;
}
.cart-btn:hover .cart-btn__inner {
  background: var(--mall-primary-soft);
}

.content {
  min-height: calc(100vh - 110px);
}

/* 窄屏：导航栏空间紧张，助手入口让位给右下悬浮球（见 AiAssistant.vue） */
@media (max-width: 768px) {
  .assistant-btn {
    display: none;
  }
}
</style>
