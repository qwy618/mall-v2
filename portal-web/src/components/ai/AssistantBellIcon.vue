<script setup lang="ts">
/**
 * 智能助手标识：柜台服务铃（设计稿 design-drafts/assistant-header-icon 01 方向）。
 *
 * 画法要点（与设计稿一致，勿随意改）：
 *  - 24 网格绘制；主体外接框占比 0.817，按 TARGET 0.90 反算归一缩放 0.90/0.817 ≈ 1.1016，
 *    使它在 16px 下与 Element Plus 购物车图标（充盈度 0.875）视觉等大。
 *  - 线宽 1.7/24（≈1.13px @16）：比默认 1.5 略粗一档，避免小尺寸描边发虚。
 *  - 顶部圆点用实心块面：16px 下描边圆会糊成一个点，实心反而清晰。
 *  - 缩放后铃顶圆点会轻微超出 viewBox（约 0.1/24），故开 overflow: visible。
 */
withDefaults(defineProps<{ size?: number }>(), { size: 16 })
</script>

<template>
  <svg
    class="assistant-bell"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
    focusable="false"
  >
    <g transform="translate(12 12) scale(1.1016) translate(-12 -12)">
      <g
        fill="none"
        stroke="currentColor"
        stroke-width="1.7"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <!-- 铃身 -->
        <path d="M4.9 18.1C4.9 11.3 8.1 4.9 12 4.9s7.1 6.4 7.1 13.2" />
        <!-- 底盘 -->
        <path d="M2.7 18.1h18.6" />
        <!-- 铃舌 -->
        <path d="M9.6 20.9a2.4 2.4 0 0 0 4.8 0" />
      </g>
      <!-- 顶钮 -->
      <circle cx="12" cy="3.3" r="1.45" fill="currentColor" />
    </g>
  </svg>
</template>

<style scoped>
.assistant-bell {
  display: block;
  overflow: visible;
}
</style>
