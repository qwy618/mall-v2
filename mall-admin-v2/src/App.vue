<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { startAdminWs, onAdminWsMessage } from '@/utils/adminWs'
import { ElNotification } from 'element-plus'

// 新订单语音播报（浏览器原生语音合成，无需音频资源）
function speakNewOrder() {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
  const u = new SpeechSynthesisUtterance('你有新的用户订单，请及时发货')
  u.lang = 'zh-CN'
  u.rate = 1
  u.pitch = 1
  window.speechSynthesis.cancel()
  window.speechSynthesis.speak(u)
}

onMounted(() => {
  // 启动全局 WebSocket（在任意后台页面都能收到新订单提醒）
  startAdminWs()
  onAdminWsMessage((msg) => {
    if (msg && msg.type === 'NEW_ORDER') {
      const p = msg.payload || {}
      ElNotification({
        title: '新订单提醒',
        message: `订单 ${p.orderSn ?? p.orderId} 已支付，金额 ¥${p.payAmount ?? p.totalAmount}，请尽快发货`,
        type: 'warning',
        duration: 8000,
        position: 'top-right',
      })
      speakNewOrder()
    }
  })
})
</script>
