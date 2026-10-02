<script setup lang="ts">
/**
 * 商品图容器：按「内容盒」（去掉原图自带的白边）渲染，紧凑不空旷。
 *
 * 原理：`picTrim` 里的离线数据记录了每张图真实内容盒的位置与尺寸。
 * 这里不用 background 定位，而是把 <img> 放大后按百分比**平移**，让内容盒正好落进容器：
 *   · 容器只关心宽高比（ratio），尺寸完全由外部布局决定；
 *   · <img> 的 width/height/left/top 全部是百分比 → 与容器像素无关，任意尺寸自适应、不变形；
 *   · 叠 mix-blend-mode: multiply，让商品图残留的白底与暖色背景融为一体。
 * 未收录的图片（如后台新上传的商品）自动回退为整图 contain，不影响功能。
 */
import { computed } from 'vue'
import { picMeta } from '@/utils/picTrim'

const props = withDefaults(
  defineProps<{
    /** 商品图地址 */
    pic?: string | null
    /** 商品名，无图时取首字做占位 */
    name?: string
    /** 图片区宽高比（宽 / 高），默认 1:1 */
    ratio?: number
    /** 内容盒装入后的缩放系数，1 = 顶格，略小于 1 留一点呼吸留白 */
    scale?: number
    /** 占位文字的额外类名（沿用各页已有样式） */
    phClass?: string
  }>(),
  { pic: '', name: '', ratio: 1, scale: 0.94, phClass: '' }
)

const crop = computed(() => picMeta(props.pic))

const boxStyle = computed(() => ({ aspectRatio: String(props.ratio) }))

/** 内容盒按 contain 装进容器并居中；所有数值换算成百分比，与容器实际像素无关 */
const cropStyle = computed<Record<string, string> | null>(() => {
  const c = crop.value
  if (!c || !c.W || !c.H) return null
  const cw = c.tw * c.W // 内容盒原始像素宽
  const ch = c.th * c.H // 内容盒原始像素高
  if (!cw || !ch) return null
  const aOuter = props.ratio || 1
  // K = 每单位容器宽度的缩放倍数（取宽/高两个方向的较小者 → contain）
  const K = props.scale * Math.min(1 / cw, 1 / (aOuter * ch))
  const imgW = c.W * K // 图宽 / 容器宽
  const imgH = c.H * K * aOuter // 图高 / 容器高
  const cwView = imgW * c.tw // 内容盒在容器中的宽度占比
  const chView = imgH * c.th // 内容盒在容器中的高度占比
  return {
    width: pct(imgW),
    height: pct(imgH),
    // 让"内容盒"在容器里居中，再把图片按内容盒在原图中的位置反向平移
    left: pct((1 - cwView) / 2 - c.x0 * imgW),
    top: pct((1 - chView) / 2 - c.y0 * imgH)
  }
})

function pct(v: number): string {
  return (v * 100).toFixed(3) + '%'
}

const ph = computed(() => (props.name ? props.name.trim().charAt(0) : '?'))
</script>

<template>
  <div class="picbox" :style="boxStyle">
    <img
      v-if="pic && cropStyle"
      class="picbox__img picbox__img--crop"
      :style="cropStyle"
      :src="pic"
      :alt="name"
      loading="lazy"
    />
    <img v-else-if="pic" class="picbox__img picbox__img--raw" :src="pic" :alt="name" loading="lazy" />
    <span v-else class="picbox__ph" :class="phClass">{{ ph }}</span>
  </div>
</template>

<style scoped>
.picbox {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  /* 暖色舞台：既是图片留白的底色，也是正片叠底的混合对象
     （isolate 让混合只发生在图片区内，不会影响卡片其他内容） */
  background: linear-gradient(160deg, #fdf8f2 0%, #f4e9dd 100%);
  isolation: isolate;
}
.picbox__img {
  display: block;
  /* 残留白底与暖色背景正片叠底，白边直接"融"进背景色 */
  mix-blend-mode: multiply;
}
/* 内容盒裁剪图：位置与尺寸全部由行内百分比控制 */
.picbox__img--crop {
  position: absolute;
  max-width: none;
  max-height: none;
}
.picbox__img--raw {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.picbox__ph {
  font-weight: 700;
  user-select: none;
}
</style>
