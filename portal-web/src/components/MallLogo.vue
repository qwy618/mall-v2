<script setup lang="ts">
/**
 * 商城标记（购物袋 + 「商」）+ 字标「商城」。
 *
 * 图形是按定稿 Logo 图逐像素量出的轮廓复刻成矢量的：原图是灰白底截图、没有透明通道，
 * 没法直接当素材（会带一块灰底）。矢量版可任意缩放、可换色、不挑分辨率。
 *
 * 量出来的关键比例（原始像素）：
 *   袋身 下宽上窄的梯形 —— 顶边 45 / 底边 52 / 高 47，四角圆角 4.5
 *   提手 23 × 17 的椭圆弧，线宽 2.6，压在袋身之下（同色所以看不出接缝）
 *   「商」白字外接框 35 × 35，居中在袋身里
 * 注意：袋顶那道白横条不是「袋口」，而是「商」自己的顶横 —— 两者等宽且相连，
 *      所以这里不另画袋口，交给字形自己交代。
 */
withDefaults(defineProps<{ size?: number }>(), { size: 36 })
</script>

<template>
  <span class="mall-logo" :style="{ fontSize: `${size}px` }">
    <svg
      class="mall-logo__mark"
      :width="(size * 56) / 58.5"
      :height="size"
      viewBox="0 0 56 58.5"
      role="img"
      aria-label="商城"
    >
      <!-- 提手：压在袋身下的扁弧（实测墨迹 23 × 8，线宽 2.6） -->
      <path
        d="M18 10.5A10.8 7.2 0 0 1 39.6 10.5"
        fill="none"
        stroke="currentColor"
        stroke-width="2.6"
        stroke-linecap="round"
      />
      <!-- 袋身：下宽上窄（顶 46 / 底 53），四角圆角 4.5，两侧各微微外鼓 -->
      <path
        d="M10.5 10H46.5Q51 10 51.4 14.4Q52 34 54 51.5Q54 57 49.5 57H6.5Q2 57 2 51.5Q2.2 34 6.1 14.4Q6 10 10.5 10Z"
        fill="currentColor"
      />
      <!-- 「商」按负空间刻出来：白色落在袋身里 -->
      <text
        x="28.5"
        y="34.5"
        text-anchor="middle"
        dominant-baseline="central"
        font-size="40"
      >
        商
      </text>
    </svg>
    <span class="mall-logo__word">商城</span>
  </span>
</template>

<style scoped>
.mall-logo {
  display: inline-flex;
  align-items: center;
  gap: 0.24em;
  color: var(--mall-logo-color, #ef7c26);
  line-height: 1;
}
.mall-logo__mark {
  display: block;
  flex: none;
  overflow: visible; /* 提手描边贴边，别被 viewBox 裁掉 */
}
.mall-logo__mark text {
  fill: #fff;
  font-family: var(--mall-font-logo);
  font-weight: 800;
}
.mall-logo__word {
  font-family: var(--mall-font-logo);
  /* 0.85em：对应定稿图里「字标墨高 43 / 袋身 47」的比例 */
  font-size: 0.85em;
  font-weight: 800;
  color: currentColor;
}
</style>
