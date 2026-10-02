<template>
  <div class="layout" :class="{ 'layout--collapsed': collapsed }">
    <aside class="layout__aside">
      <div class="layout__logo">
        <span class="layout__logo-badge">商</span>
        <div v-if="!collapsed" class="layout__logo-text">
          <span class="layout__logo-full">Mall 管理后台</span>
          <span class="layout__logo-sub">ADMIN CONSOLE</span>
        </div>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="collapsed"
        router
        class="layout__menu"
      >
        <!-- 菜单由路由表动态生成，并按当前用户角色过滤 -->
        <el-menu-item
          v-for="item in menuRoutes"
          :key="item.path"
          :index="'/' + item.path"
        >
          <el-icon v-if="item.meta?.icon">
            <component :is="iconOf(item.meta.icon)" />
          </el-icon>
          <template #title>{{ item.meta?.title }}</template>
        </el-menu-item>
      </el-menu>
    </aside>

    <section class="layout__body">
      <header class="layout__header">
        <div class="layout__left">
          <el-icon class="layout__toggle" @click="collapsed = !collapsed">
            <Expand v-if="collapsed" />
            <Fold v-else />
          </el-icon>
          <el-breadcrumb separator="/" class="layout__crumb">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ route.meta.title || '' }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <el-dropdown class="layout__user">
          <span class="layout__user-trigger">
            <el-avatar :size="32" :src="avatarSrc" class="layout__avatar">{{ avatarText }}</el-avatar>
            <span class="layout__username">{{ username }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleLogout">
                <el-icon><SwitchButton /></el-icon> 退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>

      <main class="layout__main">
        <router-view />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Component } from 'vue'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { routes } from '@/router'
import { useUserStore } from '@/stores/user'
import { filterMenuRoutes } from '@/utils/permission'
import { Expand, Fold, ArrowDown, SwitchButton } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
// 侧边栏折叠状态
const collapsed = ref(false)

// 取布局 '/' 下的 children 作为菜单数据源
const childRoutes = computed(() => {
  const root = routes.find((r) => r.path === '/')
  return root?.children ?? []
})

// 按当前用户角色 + 后端下发的可见菜单(menuIds) 过滤菜单（超级管理员 admin 始终全可见）
const menuRoutes = computed(() =>
  filterMenuRoutes(childRoutes.value, userStore.userInfo.roles, userStore.userInfo.menus)
)

// 把图标名（如 'DataLine'）映射成 @element-plus/icons-vue 里的组件
function iconOf(name?: string): Component | undefined {
  return name
    ? (ElementPlusIconsVue as Record<string, Component>)[name]
    : undefined
}

const username = computed(() => userStore.userInfo.username || 'admin')
const avatarSrc = computed(() => userStore.userInfo.avatar || undefined)
const avatarText = computed(() => username.value.charAt(0).toUpperCase())

function handleLogout() {
  userStore.userLogout()
  router.push('/login')
}
</script>

<style scoped>
.layout {
  display: flex;
  height: 100%;
}

.layout__aside {
  width: 220px;
  flex-shrink: 0;
  background: var(--admin-aside-bg);
  border-right: 1px solid var(--admin-border);
  transition: width 0.28s;
  overflow: hidden;
}

.layout--collapsed .layout__aside {
  width: 64px;
}

.layout__logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid var(--admin-border);
  overflow: hidden;
  flex-shrink: 0;
}

.layout__logo-badge {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: var(--mall-primary);
  color: #fff8f2;
  font-family: var(--mall-font-serif);
  font-weight: 700;
  font-size: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.layout__logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  white-space: nowrap;
}

.layout__logo-full {
  font-family: var(--mall-font-serif);
  font-weight: 700;
  font-size: 16px;
  color: var(--admin-text);
  letter-spacing: 0.5px;
}

.layout__logo-sub {
  font-size: 10px;
  color: var(--admin-text-light);
  letter-spacing: 2.5px;
}

.layout__menu {
  border-right: none;
  padding-top: 8px;
  background: transparent;
}

.layout__menu :deep(.el-menu-item) {
  height: 46px;
  line-height: 46px;
  margin: 2px 10px;
  border-radius: 8px;
  color: var(--admin-text-regular);
}

.layout__menu :deep(.el-menu-item .el-icon) {
  color: inherit;
}

.layout__menu :deep(.el-menu-item.is-active) {
  background: var(--admin-aside-active-bg) !important;
  color: var(--mall-price) !important;
  box-shadow: inset 3px 0 0 var(--admin-aside-active-bar);
  font-weight: 600;
}

.layout__menu :deep(.el-menu-item:not(.is-active):hover) {
  color: var(--admin-text);
  background: #f5ebdf;
}

.layout__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.layout__header {
  height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  background: var(--admin-header-bg);
  border-bottom: 1px solid var(--admin-border);
  flex-shrink: 0;
}

.layout__left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.layout__toggle {
  font-size: 20px;
  cursor: pointer;
  color: var(--admin-text-regular);
}

.layout__toggle:hover {
  color: var(--mall-primary);
}

.layout__crumb :deep(.el-breadcrumb__inner) {
  font-size: 14px;
}

.layout__username {
  font-size: 14px;
  color: var(--admin-text);
}

.layout__user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
}

.layout__avatar {
  background: var(--mall-primary-soft);
  border: 1px solid #e6cdb5;
  color: var(--mall-price);
  font-weight: 700;
}

.layout__main {
  flex: 1;
  padding: 20px;
  overflow: auto;
  background: var(--admin-bg);
}
</style>
