<script setup lang="ts">
/**
 * 一条对话消息：把 SSE 事件按到达顺序拼装的 parts 依次渲染。
 * 助手回复按顺序可能是「工具状态 → 商品卡 → 文字 → 确认卡」，顺序必须保真。
 */
import { computed } from 'vue'
import AiProductCard from './AiProductCard.vue'
import AiConfirmCard from './AiConfirmCard.vue'
import AiCitationCard from './AiCitationCard.vue'
import PicBox from '@/components/PicBox.vue'
import { AI_AVATAR } from './persona'
import type { AiCitation, AiConfirm, AiMsg, AiProduct } from '@/types/ai'

const props = defineProps<{
  msg: AiMsg
  /** 每张确认卡的状态（key = draftId），由父组件维护 */
  confirmState?: Record<string, 'pending' | 'confirmed' | 'done' | 'canceled'>
}>()

const emit = defineEmits<{
  (e: 'confirm', data: AiConfirm): void
  (e: 'cancel', data: AiConfirm): void
  (e: 'pick', item: AiProduct): void
  (e: 'cite', item: AiCitation): void
}>()

/** 工具名 → 面向用户的状态文案（禁术语、禁英文） */
const TOOL_LABEL: Record<string, string> = {
  search_products: '正在搜索商品',
  show_products: '正在为您挑选',
  get_product_detail: '正在查看商品详情',
  add_to_cart: '正在加入购物车',
  list_cart: '正在查看购物车',
  preview_order: '正在核算订单金额',
  place_order: '正在为您下单',
  recommend_for_me: '正在为您找相似好物',
  search_knowledge: '正在查看商品口碑',
}

function toolLabel(name: string): string {
  return TOOL_LABEL[name] || '正在处理'
}

function money(v?: number | null): string {
  return Number(v ?? 0).toFixed(2)
}

function confirmStateOf(draftId: string): 'pending' | 'confirmed' | 'done' | 'canceled' {
  return props.confirmState?.[draftId] || 'pending'
}

/** 只有最后一条助手消息且仍在流式时显示光标 */
const showCursor = () => props.msg.role === 'assistant' && props.msg.streaming === true

/**
 * 「工具状态」是进行中的瞬时提示，不是对话内容，不能永久留在气泡里。
 *
 * 后端只在工具**发起时**发一次 tool 事件、从不发结束事件（见 mall-ai-agent/app/main.py），
 * 所以收尾信号只能由前端推断：工具还在跑 ⇔ 它是当前最后一段、且本轮仍在流式。
 * 一旦后面来了新内容（文字 / 商品卡 / 确认卡 / 下一个工具），就说明这个工具已经结束，
 * 必须收起 —— 否则会出现「已经回复了『没有找到商品』，头上却还挂着『正在搜索商品…』」的假进行中。
 */
const visibleParts = computed(() =>
  props.msg.parts.filter(
    (p, i) => p.kind !== 'tool' || (props.msg.streaming === true && i === props.msg.parts.length - 1),
  ),
)

/** 有没有真正可展示的内容（用于避免收起状态提示后留下一个空气泡） */
const hasContent = computed(() => visibleParts.value.length > 0)

/** 用户消息只有一段文本；用函数取值（模板里不支持 TS 类型断言） */
function userText(): string {
  const p = props.msg.parts[0]
  return p && p.kind === 'text' ? p.text : ''
}
</script>

<template>
  <div
    v-if="msg.role === 'user' || hasContent || msg.streaming"
    class="bubble"
    :class="[`bubble--${msg.role}`, { 'bubble--error': msg.error }]"
    :style="{ '--ai-avatar-char': `'${AI_AVATAR}'` }"
  >
    <!-- 用户消息 -->
    <template v-if="msg.role === 'user'">
      <div class="bubble__text">{{ userText() }}</div>
    </template>

    <!-- 助手消息：按 parts 顺序渲染 -->
    <template v-else>
      <template v-for="(part, i) in visibleParts" :key="i">
        <!-- 纯文本 -->
        <div v-if="part.kind === 'text' && part.text" class="bubble__text">
          {{ part.text }}<span v-if="showCursor() && i === visibleParts.length - 1" class="caret" />
        </div>

        <!-- 工具调用状态气泡 -->
        <div v-else-if="part.kind === 'tool'" class="status">
          <span class="status__dot" />
          <span>{{ toolLabel(part.name) }}…</span>
        </div>

        <!-- 商品卡片组 -->
        <div v-else-if="part.kind === 'products'" class="cards">
          <AiProductCard
            v-for="it in part.items"
            :key="it.id"
            :item="it"
            @pick="(p) => emit('pick', p)"
          />
        </div>

        <!-- 单品详情卡 -->
        <div v-else-if="part.kind === 'product'" class="cards">
          <AiProductCard :item="part.item" @pick="(p) => emit('pick', p)" />
        </div>

        <!-- 加购成功 -->
        <div v-else-if="part.kind === 'cart'" class="added">
          <div class="added__pic">
            <PicBox :pic="''" :name="part.data.productName" :ratio="1" :scale="0.9" />
          </div>
          <div class="added__body">
            <p class="added__title">已加入购物车</p>
            <p class="added__name">{{ part.data.productName }}</p>
            <p class="added__meta">
              <span class="added__price">￥{{ money(part.data.price) }}</span>
              <span class="added__qty">×{{ part.data.quantity ?? 1 }}</span>
            </p>
          </div>
        </div>

        <!-- 订单确认卡 -->
        <AiConfirmCard
          v-else-if="part.kind === 'confirm'"
          :data="part.data"
          :state="confirmStateOf(part.data.draftId)"
          @confirm="emit('confirm', part.data)"
          @cancel="emit('cancel', part.data)"
        />

        <!-- 下单成功卡 -->
        <div v-else-if="part.kind === 'order'" class="order">
          <p class="order__title">下单成功</p>
          <p class="order__sn">订单号：{{ part.data.orderSn || part.data.orderId }}</p>
          <p class="order__pay">
            应付金额 <span class="order__amount">￥{{ money(part.data.payAmount) }}</span>
          </p>
        </div>

        <!-- 引用卡片（M3.4）：回答口碑/体验类问题时，标注信息来自哪些商品 -->
        <AiCitationCard
          v-else-if="part.kind === 'citation'"
          :items="part.items"
          @cite="(it) => emit('cite', it)"
        />
      </template>
    </template>
  </div>
</template>

<style scoped>
.bubble {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 100%;
  animation: bubble-in 0.24s ease-out both;
}
@keyframes bubble-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

/* ---------- 用户气泡 ---------- */
.bubble--user {
  align-items: flex-end;
}
.bubble--user .bubble__text {
  background: var(--mall-primary);
  color: #fff;
  border-radius: var(--mall-radius) 2px var(--mall-radius) var(--mall-radius);
  padding: 8px 12px;
  font-size: 13px;
  line-height: 1.55;
  max-width: 82%;
  word-break: break-word;
}

/* ---------- 助手 ----------
 * 用 grid 而不是 flex row：头像占第 1 列，parts 全部落到第 2 列并各自成行。
 * 这样无需给模板加包裹层（parts 是 v-for 直出的），头像也不会被当成一个 part。
 */
.bubble--assistant {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr);
  column-gap: 8px;
  row-gap: 8px;
  align-items: start;
}
.bubble--assistant > * {
  grid-column: 2;
  min-width: 0;
}
/* 头像：跨越所有行，只出现在第一行左侧。
   头像字走 CSS 变量（persona.ts 注入），改名不会漏掉这一处；
   字族用品牌标记那套粗黑体 —— 与头部 Logo 同源，中文字形也比衬线清楚。 */
.bubble--assistant::before {
  content: var(--ai-avatar-char, '满');
  grid-column: 1;
  grid-row: 1;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--mall-primary-gradient);
  color: #fff;
  font-family: var(--mall-font-logo);
  font-weight: 800;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.bubble--assistant .bubble__text {
  background: var(--mall-card);
  border: 1px solid var(--mall-border);
  color: var(--mall-text);
  border-radius: 2px var(--mall-radius) var(--mall-radius) var(--mall-radius);
  padding: 9px 12px;
  font-size: 13px;
  line-height: 1.72;
  white-space: pre-wrap;
  word-break: break-word;
  max-width: 100%;
}
.bubble--error .bubble__text {
  border-color: #e8c4c4;
  background: #fdf6f6;
  color: #9c4a4a;
}

/* 打字光标 */
.caret {
  display: inline-block;
  width: 5px;
  height: 13px;
  margin-left: 2px;
  vertical-align: -2px;
  background: var(--mall-primary);
  animation: blink 1s step-start infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}

/* 工具状态 */
.status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--mall-text-light);
  padding: 3px 0;
}
.status__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--mall-primary-light);
  animation: pulse 1.1s ease-in-out infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 0.35;
    transform: scale(0.85);
  }
  50% {
    opacity: 1;
    transform: scale(1);
  }
}

/* 卡片容器 */
.cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 100%;
}

/* 加购成功 */
.added {
  display: flex;
  gap: 10px;
  align-items: center;
  width: 100%;
  max-width: 100%;
  padding: 8px 10px;
  background: var(--mall-primary-soft);
  border: 1px solid #efd9cb;
  border-radius: var(--mall-radius);
}
.added__pic {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: var(--mall-radius-sm);
  overflow: hidden;
}
.added__body {
  flex: 1;
  min-width: 0;
}
.added__title {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: var(--mall-primary-dark);
}
.added__name {
  margin: 2px 0 1px;
  font-size: 12px;
  color: var(--mall-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.added__meta {
  margin: 0;
  display: flex;
  gap: 8px;
  font-size: 12px;
}
.added__price {
  color: var(--mall-price);
  font-weight: 600;
}
.added__qty {
  color: var(--mall-text-light);
}

/* 下单成功 */
.order {
  width: 100%;
  max-width: 100%;
  padding: 12px;
  background: #f2f8f3;
  border: 1px solid #cfe3d2;
  border-radius: var(--mall-radius);
}
.order__title {
  margin: 0 0 4px;
  font-family: var(--mall-font-serif);
  font-size: 14px;
  font-weight: 700;
  color: #2f7d46;
}
.order__sn {
  margin: 0 0 2px;
  font-size: 12px;
  color: var(--mall-text-regular);
  word-break: break-all;
}
.order__pay {
  margin: 0;
  font-size: 12px;
  color: var(--mall-text-regular);
}
.order__amount {
  color: var(--mall-price);
  font-size: 15px;
  font-weight: 700;
  margin-left: 2px;
}
</style>
