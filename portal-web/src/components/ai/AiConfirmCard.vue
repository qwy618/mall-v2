<script setup lang="ts">
/**
 * 订单确认卡：preview_order 生成的草稿展示。
 * 用户点「确认下单」→ 由父组件发一条「系统指令」给助手，LLM 才会调 place_order。
 * 卡片金额来自后端 /order/preview（与真正下单同源），前端不做任何二次计算。
 */
import PicBox from '@/components/PicBox.vue'
import type { AiConfirm } from '@/types/ai'

defineProps<{
  data: AiConfirm
  /** pending 待确认 / confirmed 提交中 / done 已下单 / canceled 已取消 */
  state?: 'pending' | 'confirmed' | 'done' | 'canceled'
}>()

const emit = defineEmits<{ (e: 'confirm'): void; (e: 'cancel'): void }>()

function money(v?: number | null): string {
  return Number(v ?? 0).toFixed(2)
}
</script>

<template>
  <div class="ccard" :class="{ 'ccard--done': state === 'done', 'ccard--canceled': state === 'canceled' }">
    <div class="ccard__head">
      <span class="ccard__title">订单确认</span>
      <span v-if="state === 'done'" class="ccard__badge ccard__badge--done">已下单</span>
      <span v-else-if="state === 'confirmed'" class="ccard__badge">提交中</span>
      <span v-else-if="state === 'canceled'" class="ccard__badge">已取消</span>
    </div>

    <div class="ccard__addr">
      <span class="ccard__label">收货信息</span>
      <span class="ccard__addr-text">{{ data.addressText || '未获取到地址' }}</span>
    </div>

    <div class="ccard__items">
      <div v-for="(it, i) in data.items" :key="i" class="citem">
        <div class="citem__pic">
          <PicBox :pic="it.pic" :name="it.name" :ratio="1" :scale="0.9" />
        </div>
        <div class="citem__body">
          <p class="citem__name">{{ it.name }}</p>
          <p v-if="it.promotion" class="citem__promo">{{ it.promotion }}</p>
          <div class="citem__foot">
            <span class="citem__price">￥{{ money(it.price) }}</span>
            <span class="citem__qty">×{{ it.quantity ?? 1 }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="ccard__amounts">
      <div class="crow">
        <span>商品合计</span>
        <span>￥{{ money(data.totalAmount) }}</span>
      </div>
      <div v-if="Number(data.promotionAmount ?? 0) > 0" class="crow crow--cut">
        <span>会员优惠</span>
        <span>-￥{{ money(data.promotionAmount) }}</span>
      </div>
      <div class="crow crow--pay">
        <span>应付金额</span>
        <span class="ccard__pay">￥{{ money(data.payAmount) }}</span>
      </div>
    </div>

    <div v-if="state === 'pending'" class="ccard__actions">
      <button type="button" class="cbtn cbtn--ghost" @click="emit('cancel')">再想想</button>
      <button type="button" class="cbtn cbtn--primary" @click="emit('confirm')">确认下单</button>
    </div>
    <p v-else class="ccard__tip">
      {{
        state === 'done'
          ? '订单已提交，可到「我的订单」查看'
          : state === 'confirmed'
            ? '正在为您提交订单…'
            : '已取消本次下单'
      }}
    </p>
  </div>
</template>

<style scoped>
.ccard {
  background: var(--mall-card);
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius);
  padding: 12px;
  box-shadow: var(--mall-shadow);
}
.ccard--done {
  border-color: #cfe3d2;
}
.ccard--canceled {
  opacity: 0.72;
}
.ccard__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.ccard__title {
  font-family: var(--mall-font-serif);
  font-size: 14px;
  font-weight: 700;
  color: var(--mall-text);
  letter-spacing: 0.5px;
}
.ccard__badge {
  font-size: 11px;
  color: var(--mall-text-light);
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-sm);
  padding: 0 6px;
}
.ccard__badge--done {
  color: #2f7d46;
  border-color: #cfe3d2;
  background: #f0f7f1;
}
.ccard__addr {
  display: flex;
  gap: 8px;
  padding: 8px;
  background: var(--mall-bg);
  border-radius: var(--mall-radius-sm);
  margin-bottom: 10px;
}
.ccard__label {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--mall-text-light);
  line-height: 1.6;
}
.ccard__addr-text {
  font-size: 12px;
  color: var(--mall-text-regular);
  line-height: 1.6;
}
.ccard__items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
}
.citem {
  display: flex;
  gap: 8px;
}
.citem__pic {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border-radius: var(--mall-radius-sm);
  overflow: hidden;
}
.citem__body {
  flex: 1;
  min-width: 0;
}
.citem__name {
  margin: 0;
  font-size: 12px;
  color: var(--mall-text);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.citem__promo {
  margin: 2px 0 0;
  font-size: 11px;
  color: var(--mall-primary);
}
.citem__foot {
  display: flex;
  justify-content: space-between;
  margin-top: 3px;
  font-size: 12px;
}
.citem__price {
  color: var(--mall-price);
  font-weight: 600;
}
.citem__qty {
  color: var(--mall-text-light);
}
.ccard__amounts {
  border-top: 1px dashed var(--mall-border);
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.crow {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--mall-text-regular);
}
.crow--cut span:last-child {
  color: var(--mall-primary);
}
.crow--pay {
  margin-top: 2px;
  font-size: 13px;
  color: var(--mall-text);
  font-weight: 600;
}
.ccard__pay {
  color: var(--mall-price);
  font-size: 16px;
  font-weight: 700;
}
.ccard__actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.cbtn {
  flex: 1;
  height: 34px;
  border-radius: var(--mall-radius-sm);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: filter 0.18s ease, background 0.18s ease, border-color 0.18s ease;
}
.cbtn--ghost {
  background: #fff;
  color: var(--mall-text-regular);
  border-color: var(--mall-border);
}
.cbtn--ghost:hover {
  color: var(--mall-primary);
  border-color: var(--mall-primary-light);
  background: var(--mall-primary-soft);
}
.cbtn--primary {
  background: var(--mall-primary-gradient);
  color: #fff;
  box-shadow: 0 4px 10px rgba(192, 116, 79, 0.28);
}
.cbtn--primary:hover {
  filter: brightness(1.05);
}
.ccard__tip {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--mall-text-light);
  text-align: center;
}
</style>
