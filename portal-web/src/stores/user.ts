import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const nickname = ref<string>(localStorage.getItem('nickname') || '')
  const phone = ref<string>(localStorage.getItem('phone') || '')
  const icon = ref<string>(localStorage.getItem('icon') || '')

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)
  }

  function setNickname(n: string) {
    nickname.value = n
    localStorage.setItem('nickname', n)
  }

  function setPhone(p: string) {
    phone.value = p
    localStorage.setItem('phone', p)
  }

  function setIcon(i: string) {
    icon.value = i
    localStorage.setItem('icon', i)
  }

  function logout() {
    token.value = ''
    nickname.value = ''
    phone.value = ''
    icon.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('nickname')
    localStorage.removeItem('phone')
    localStorage.removeItem('icon')
  }

  return { token, nickname, phone, icon, setToken, setNickname, setPhone, setIcon, logout }
})
