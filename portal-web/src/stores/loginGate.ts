import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 登录引导弹窗状态：
 * 需要登录才能访问的页面/操作，不再硬跳登录页，而是打开一个暖色弹窗引导用户去登录。
 * - redirect：登录成功后希望返回的路径（可选）
 * - message： 弹窗副标题（可自定义，如"登录已过期，请重新登录"）
 * - title：   弹窗标题（可选，缺省时组件用默认文案）
 */
export const useLoginGate = defineStore('loginGate', () => {
  const visible = ref(false)
  const redirect = ref('')
  const message = ref('')
  const title = ref('')

  function require_(path = '', msg = '', tip = '') {
    redirect.value = path
    message.value = msg
    title.value = tip
    visible.value = true
  }

  function close() {
    visible.value = false
  }

  return { visible, redirect, message, title, require: require_, close }
})
