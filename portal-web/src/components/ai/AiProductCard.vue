<script setup lang="ts">
/** 商品小卡：搜索结果 / 单品详情 / 推荐 共用。点击跳商品详情页（/product?pid=）。 */
import { useRouter } from 'vue-router'
import PicBox from '@/components/PicBox.vue'
import type { AiProduct } from '@/types/ai'

const props = defineProps<{ item: AiProduct }>()
const emit = defineEmits<{ (e: 'pick', item: AiProduct): void }>()

const router = useRouter()

function money(v?: number | null): string {
  return Number(v ?? 0).toFixed(2)
}

function open() {
  emit('pick', props.item)
  router.push({ path: '/product', query: { pid: String(props.item.id) } })
}
</script>

<template>
  <div class="pcard" @click="open">
    <div class="pcard__pic">
      <PicBox :pic="item.pic" :name="item.name" :ratio="1" :scale="0.9" />
    </div>
    <div class="pcard__body">
      <p class="pcard__name">{{ item.name }}</p>
      <p v-if="item.reason" class="pcard__reason">{{ item.reason }}</p>
      <p v-else-if="item.subTitle" class="pcard__sub">{{ item.subTitle }}</p>
      <div class="pcard__foot">
        <span class="pcard__price"><i>￥</i>{{ money(item.price) }}</span>
        <span class="pcard__go">去看看</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pcard {
  display: flex;
  gap: 10px;
  padding: 8px;
  background: var(--mall-card);
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius);
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}
.pcard:hover {
  border-color: var(--mall-primary-light);
  box-shadow: var(--mall-shadow);
}
.pcard__pic {
  width: 62px;
  height: 62px;
  flex-shrink: 0;
  border-radius: var(--mall-radius-sm);
  overflow: hidden;
}
.pcard__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.pcard__name {
  margin: 0 0 3px;
  font-size: 13px;
  font-weight: 600;
  color: var(--mall-text);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.pcard__reason {
  margin: 0 0 3px;
  font-size: 11px;
  color: var(--mall-primary);
  background: var(--mall-primary-soft);
  border-radius: var(--mall-radius-sm);
  padding: 1px 6px;
  align-self: flex-start;
}
.pcard__sub {
  margin: 0 0 3px;
  font-size: 11px;
  color: var(--mall-text-light);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pcard__foot {
  margin-top: auto;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.pcard__price {
  color: var(--mall-price);
  font-size: 15px;
  font-weight: 700;
}
.pcard__price i {
  font-style: normal;
  font-size: 12px;
  margin-right: 1px;
}
.pcard__go {
  font-size: 11px;
  color: var(--mall-text-light);
}
</style>
