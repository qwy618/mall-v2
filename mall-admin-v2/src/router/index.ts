import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import Layout from '@/layout/index.vue'
import '@/types/router' // 触发 RouteMeta 类型增强

/**
 * 路由表。
 * - meta.title：layout 标题栏读取
 * - meta.icon：菜单图标名（对应 @element-plus/icons-vue 导出的组件名）
 * - meta.roles：允许访问该菜单的角色 code 列表
 *     · 不填 / 空数组 = 所有已登录用户可见
 *     · 填了 = 仅列出的角色可见（超级管理员 admin 始终可见，见 utils/permission）
 */
const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', hidden: true },
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '首页', icon: 'DataLine' },
      },
      {
        path: 'brand',
        name: 'Brand',
        component: () => import('@/views/brand/index.vue'),
        meta: { title: '品牌管理', icon: 'Goods', roles: ['product'] },
      },
      {
        path: 'category',
        name: 'Category',
        component: () => import('@/views/category/index.vue'),
        meta: { title: '商品分类', icon: 'Menu', roles: ['product'] },
      },
      {
        path: 'product',
        name: 'Product',
        component: () => import('@/views/product/index.vue'),
        meta: { title: '商品管理', icon: 'ShoppingCart', roles: ['product'] },
      },
      {
        path: 'attribute',
        name: 'Attribute',
        component: () => import('@/views/product/attribute.vue'),
        meta: { title: '商品属性', icon: 'Collection', roles: ['product'] },
      },
      {
        path: 'order',
        name: 'Order',
        component: () => import('@/views/order/index.vue'),
        meta: { title: '订单管理', icon: 'Tickets', roles: ['admin', 'product'] },
      },
      {
        path: 'coupon',
        name: 'Coupon',
        component: () => import('@/views/coupon/index.vue'),
        meta: { title: '优惠券管理', icon: 'Discount', roles: ['product'] },
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('@/views/system/index.vue'),
        meta: { title: '系统管理', icon: 'Setting', roles: ['admin'] },
      },
      {
        path: 'comment',
        name: 'Comment',
        component: () => import('@/views/comment/index.vue'),
        meta: { title: '评价管理', icon: 'ChatLineSquare', roles: ['admin'] },
      },
      {
        path: 'return',
        name: 'OrderReturn',
        component: () => import('@/views/return/index.vue'),
        meta: { title: '售后管理', icon: 'Refund', roles: ['admin', 'product'] },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 导出供 layout 动态生成菜单、guard 做权限判断时使用
export { routes }
export default router
