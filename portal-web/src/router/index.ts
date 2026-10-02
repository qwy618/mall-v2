import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useLoginGate } from '@/stores/loginGate'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/login/index.vue'),
      meta: { hideHeader: true },
    },
    {
      path: '/register',
      name: 'Register',
      component: () => import('@/views/register/index.vue'),
      meta: { hideHeader: true },
    },
    { path: '/', redirect: '/product' },
    {
      path: '/product',
      name: 'Product',
      component: () => import('@/views/product/index.vue'),
    },
    {
      path: '/search',
      name: 'Search',
      component: () => import('@/views/search/index.vue'),
    },
    {
      path: '/coupon',
      name: 'Coupon',
      component: () => import('@/views/coupon/index.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/order/confirm',
      name: 'OrderConfirm',
      component: () => import('@/views/order/confirm.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/order/list',
      name: 'OrderList',
      component: () => import('@/views/order/list.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/order/detail',
      name: 'OrderDetail',
      component: () => import('@/views/order/detail.vue'),
      meta: { requiresAuth: true },
    },
    {
      // 购物车对游客放开：未登录读本地暂存车渲染，结算时再引导登录
      path: '/cart',
      name: 'Cart',
      component: () => import('@/views/cart/index.vue'),
    },
    {
      path: '/review/submit',
      name: 'ReviewSubmit',
      component: () => import('@/views/review/submit.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/member',
      name: 'MemberCenter',
      component: () => import('@/views/member/index.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/member/change-password',
      name: 'ChangePassword',
      component: () => import('@/views/member/change-password.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/member/address',
      name: 'MemberAddress',
      component: () => import('@/views/member/address.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/member/favorite',
      name: 'MemberFavorite',
      component: () => import('@/views/member/favorite.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/member/integration',
      name: 'MemberIntegration',
      component: () => import('@/views/member/integration.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/return/apply',
      name: 'ReturnApply',
      component: () => import('@/views/return/apply.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/return/list',
      name: 'ReturnList',
      component: () => import('@/views/return/list.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/return/detail',
      name: 'ReturnDetail',
      component: () => import('@/views/return/detail.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  if (to.meta.requiresAuth && !userStore.token) {
    // 需登录页面：不硬跳登录页，改为弹窗引导去登录
    useLoginGate().require(to.fullPath)
    if (!from.name) {
      // 直接输网址进入受保护页 → 回首页并弹窗（避免白屏）
      next('/product')
    } else {
      // 页内点击跳转 → 取消导航，留在原页弹窗
      next(false)
    }
    return
  }
  next()
})

export default router
