<script setup lang="ts">
/**
 * 引用卡片（M3.4）：助手回答「口碑 / 使用体验」类问题时的信息来源。
 *
 * 数据来自后端 `citation` 事件（见 mall-ai-agent/app/main.py）：
 *   { productId, name, source, starAvg, reviewCount }
 *
 * ⚠️ 两条硬约束：
 *  1. `source === 'product_profile'`（商品档案）的条目 **没有评价数据** →
 *     `starAvg` / `reviewCount` 为 `null`，必须判空后走「商品信息」标签，
 *     否则会渲染出「0.0 分 · 0 条评价」这种凭空捏造的差评观感。
 *  2. **只展示面向用户的字段**：不出现 source / docType / score / 索引时间等内部标识。
 *
 * 交互：点击整行 → emit `cite`，由父组件（AiAssistant）负责「关面板 + 跳商品详情」。
 * 组件自身**不做路由跳转**：导航是页面级动作，统一由父组件处理，避免同一跳转被重复触发。
 */
import type { AiCitation } from '@/types/ai'

const props = defineProps<{ items: AiCitation[] }>()
const emit = defineEmits<{ (e: 'cite', item: AiCitation): void }>()

/** 有评价聚合数据才算「口碑」来源；否则退化为「商品信息」 */
function hasReviews(it: AiCitation): boolean {
  return it.starAvg != null && it.reviewCount != null
}

function score(v?: number | null): string {
  return Number(v ?? 0).toFixed(1)
}

/** 四舍五入到整星，决定点亮几颗（限制在 0~5） */
function litStars(v?: number | null): number {
  return Math.max(0, Math.min(5, Math.round(Number(v ?? 0))))
}

function open(it: AiCitation) {
  emit('cite', it)
}
</script>

<template>
  <div v-if="props.items.length" class="cite">
    <p class="cite__head">参考了这些商品</p>
    <ul class="cite__list">
      <li v-for="it in props.items" :key="it.productId" class="cite__row" @click="open(it)">
        <div class="cite__main">
          <p class="cite__name">{{ it.name }}</p>
          <p v-if="hasReviews(it)" class="cite__meta">
            <span class="cite__stars">
              <i v-for="n in 5" :key="n" :class="{ 'is-on': n <= litStars(it.starAvg) }">★</i>
            </span>
            <span class="cite__score">{{ score(it.starAvg) }}</span>
            <span class="cite__count">{{ it.reviewCount }} 条评价</span>
          </p>
          <p v-else class="cite__meta">
            <span class="cite__tag">商品信息</span>
          </p>
        </div>
        <span class="cite__go">去看看</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
/* 整块用暖色浅底 + 左侧竖线，与「加购成功」卡同一套视觉语言，一眼区分于商品卡 */
.cite {
  width: 100%;
  max-width: 92%;
  padding: 10px 12px;
  background: var(--mall-primary-soft);
  border-left: 3px solid var(--mall-primary-light);
  border-radius: var(--mall-radius);
}

.cite__head {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: var(--mall-primary-dark);
}

.cite__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cite__row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: var(--mall-card);
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-sm);
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}
.cite__row:hover {
  border-color: var(--mall-primary-light);
  box-shadow: var(--mall-shadow);
}

.cite__main {
  flex: 1;
  min-width: 0;
}

.cite__name {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--mall-text);
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cite__meta {
  margin: 3px 0 0;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--mall-text-light);
}

.cite__stars {
  display: inline-flex;
  gap: 1px;
}
.cite__stars i {
  font-style: normal;
  font-size: 11px;
  line-height: 1;
  color: var(--mall-border);
}
.cite__stars i.is-on {
  color: var(--mall-primary);
}

.cite__score {
  color: var(--mall-price);
  font-weight: 700;
}

.cite__tag {
  font-size: 11px;
  color: var(--mall-text-light);
  background: var(--mall-bg);
  border-radius: var(--mall-radius-sm);
  padding: 1px 6px;
}

.cite__go {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--mall-text-light);
}
</style>
