<template>
  <div class="page" v-loading="loading">
    <div class="crumb">
      <span class="link" @click="router.push('/order/list')">我的订单</span>
      <span class="sep">/</span>
      <span>订单详情</span>
    </div>
    <h2 class="page-title">订单详情</h2>

    <template v-if="detail">
      <div class="box status-box">
        <div class="status-left">
          <div class="status-text">{{ statusText(detail.order.status) }}</div>
          <div v-if="detail.order.status === 0 && remainingMs > 0" class="status-desc">
            请在
            <span class="countdown" :class="{ urgent: isUrgent }">{{ countdownText }}</span>
            内完成支付，超时订单将自动取消
          </div>
          <div v-else-if="detail.order.status === 0 && remainingMs <= 0" class="status-desc">
            订单支付已超时，系统正在关闭该订单…
          </div>
          <div v-else class="status-desc">{{ statusDesc(detail.order.status) }}</div>
        </div>
        <div class="status-actions">
          <el-button
            v-if="detail.order.status === 0"
            type="primary"
            :loading="acting"
            :disabled="remainingMs <= 0"
            @click="pay"
          >立即支付</el-button>
          <el-button
            v-if="detail.order.status === 0"
            :loading="acting"
            @click="cancel"
          >取消订单</el-button>
          <el-button
            v-if="detail.order.status === 2"
            type="primary"
            :loading="acting"
            @click="confirm"
          >确认收货</el-button>
        </div>
      </div>

      <div class="box">
        <div class="box-title">收货信息</div>
        <div class="info-grid">
          <div><span class="lbl">收货人</span>{{ detail.order.receiverName }}</div>
          <div><span class="lbl">手机号</span>{{ detail.order.receiverPhone }}</div>
          <div class="full">
            <span class="lbl">地址</span>
            {{ detail.order.receiverProvince }}{{ detail.order.receiverCity
            }}{{ detail.order.receiverDistrict }} {{ detail.order.receiverDetailAddress }}
          </div>
        </div>
      </div>

      <div class="box">
        <div class="box-title">商品清单</div>
        <div class="goods-list">
          <div v-for="it in detail.items" :key="it.id" class="goods-row">
            <PicBox
              class="g-img"
              :pic="it.productPic"
              :name="it.productName"
              :ratio="1"
              :scale="1"
              ph-class="img-ph"
            />
            <div class="g-info">
              <div class="g-name">{{ it.productName }}</div>
              <div v-if="it.spData" class="g-spec">{{ formatSpec(it.spData) }}</div>
              <div class="g-sn">SKU：{{ it.skuCode }}</div>
            </div>
            <div class="g-price">￥{{ money(it.price) }}</div>
            <div class="g-qty">x{{ it.quantity }}</div>
            <div class="g-sub">￥{{ money((it.price ?? 0) * (it.quantity ?? 0)) }}</div>
            <div class="g-act">
              <el-button
                v-if="detail.order.status === 3 && it.commentStatus !== 1"
                size="small"
                type="primary"
                link
                @click.stop="goReview(it)"
              >评价</el-button>
              <span
                v-else-if="detail.order.status === 3 && it.commentStatus === 1"
                class="g-reviewed"
              >已评价</span>
              <el-button
                v-if="detail.order.status === 3"
                size="small"
                type="warning"
                link
                @click.stop="goReturn"
              >申请售后</el-button>
            </div>
          </div>
        </div>
      </div>

      <div class="box">
        <div class="box-title">金额信息</div>
        <div class="settle-row"><span>商品合计</span><span>￥{{ money(detail.order.totalAmount) }}</span></div>
        <div class="settle-row"><span>运费</span><span>￥{{ money(detail.order.freightAmount) }}</span></div>
        <div class="settle-row" v-if="(detail.order.promotionAmount ?? 0) > 0">
          <span>会员折扣</span><span>￥{{ money(detail.order.promotionAmount) }}</span>
        </div>
        <div class="settle-row" v-if="(detail.order.couponAmount ?? 0) > 0">
          <span>优惠券抵扣</span><span>￥{{ money(detail.order.couponAmount) }}</span>
        </div>
        <div class="settle-row" v-if="(detail.order.integrationAmount ?? 0) > 0">
          <span>积分抵扣（{{ detail.order.useIntegration ?? 0 }} 积分）</span>
          <span>￥{{ money(detail.order.integrationAmount) }}</span>
        </div>
        <div class="settle-row total"><span>实付金额</span><span class="pay-num">￥{{ money(detail.order.payAmount) }}</span></div>
      </div>

      <div class="box">
        <div class="box-title">订单信息</div>
        <div class="info-grid">
          <div><span class="lbl">订单号</span>{{ detail.order.orderSn }}</div>
          <div><span class="lbl">创建时间</span>{{ fmtTime(detail.order.createTime) }}</div>
          <div v-if="detail.order.paymentTime"><span class="lbl">支付时间</span>{{ fmtTime(detail.order.paymentTime) }}</div>
          <div v-if="detail.order.deliveryTime"><span class="lbl">发货时间</span>{{ fmtTime(detail.order.deliveryTime) }}</div>
          <div v-if="detail.order.receiveTime"><span class="lbl">收货时间</span>{{ fmtTime(detail.order.receiveTime) }}</div>
        </div>
      </div>
    </template>

    <el-empty v-else-if="!loading" description="订单不存在或已删除" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getOrderDetail, payOrder, cancelOrder, confirmReceived } from '@/apis/order'
import { ORDER_PAY_TIMEOUT_MS } from '@/types/order'
import { formatSpec } from '@/utils/spec'
import type { OrderDetailVO, OrderItem } from '@/types/order'
import PicBox from '@/components/PicBox.vue'

const route = useRoute()
const router = useRouter()

const detail = ref<OrderDetailVO | null>(null)
const loading = ref(false)
const acting = ref(false)

// 30 分钟支付倒计时（基于后端 createTime + ORDER_PAY_TIMEOUT_MS）
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | undefined

// 截止时间戳：createTime(ISO 带 T) + 30 分钟
const deadlineMs = computed(() => {
  const ct = detail.value?.order.createTime
  if (!ct) return 0
  const t = new Date(ct.replace(' ', 'T')).getTime()
  return Number.isNaN(t) ? 0 : t + ORDER_PAY_TIMEOUT_MS
})

// 剩余毫秒（仅待支付态有意义）
const remainingMs = computed(() => {
  if (!detail.value || detail.value.order.status !== 0) return 0
  return Math.max(0, deadlineMs.value - now.value)
})

// 剩余 ≤5 分钟进入紧急态（红色）
const isUrgent = computed(() => remainingMs.value > 0 && remainingMs.value <= 5 * 60 * 1000)

const countdownText = computed(() => formatRemaining(remainingMs.value))

function formatRemaining(ms: number) {
  const total = Math.floor(ms / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)}`
}

function money(n?: number) {
  return (Number(n) || 0).toFixed(2)
}
function fmtTime(t?: string) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}
function statusText(s: number) {
  return ['待支付', '待发货', '待收货', '已完成', '已取消', '已失效'][s] ?? '未知'
}
function statusDesc(s: number) {
  return ['请尽快完成支付', '商家正在打包发货', '包裹已发出，请注意查收', '交易完成', '订单已取消', '订单无法履约，已作废并退款'][s] ?? ''
}

async function fetchDetail() {
  const orderId = Number(route.query.orderId)
  if (!orderId) return
  loading.value = true
  try {
    detail.value = await getOrderDetail(orderId)
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function pay() {
  if (!detail.value) return
  acting.value = true
  try {
    await payOrder(detail.value.order.id)
    ElMessage.success('支付成功')
    fetchDetail()
  } finally {
    acting.value = false
  }
}
async function cancel() {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm('确定取消该订单？取消后将恢复库存', '提示', { type: 'warning' })
  } catch {
    return
  }
  acting.value = true
  try {
    await cancelOrder(detail.value.order.id)
    ElMessage.success('订单已取消')
    fetchDetail()
  } finally {
    acting.value = false
  }
}
async function confirm() {
  if (!detail.value) return
  acting.value = true
  try {
    await confirmReceived(detail.value.order.id)
    ElMessage.success('已确认收货')
    fetchDetail()
  } finally {
    acting.value = false
  }
}

function goReview(it: OrderItem) {
  router.push({
    path: '/review/submit',
    query: {
      orderItemId: it.id,
      productName: it.productName,
      productPic: it.productPic,
      spec: it.spData,
    },
  })
}

function goReturn() {
  if (detail.value) {
    router.push({ path: '/return/apply', query: { orderId: detail.value.order.id } })
  }
}

onMounted(() => {
  fetchDetail()
  timer = setInterval(() => {
    now.value = Date.now()
  }, 1000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})

// 倒计时归零（待支付 -> 剩余≤0）：前端判定超时，禁用支付并同步后端真实状态
// （后端 RabbitMQ 延迟队列会把订单置为已取消，这里主动刷新一次拿到最新 status）
watch(remainingMs, (n, o) => {
  if (o > 0 && n <= 0 && detail.value?.order.status === 0) {
    fetchDetail()
    ElMessage.warning('订单支付已超时，系统已自动取消')
  }
})
</script>

<style scoped>
.page {
  padding: 20px 24px 40px;
  background: var(--mall-bg);
  min-height: calc(100vh - 60px);
}
.crumb {
  font-size: 13px;
  color: var(--mall-text-light);
  margin-bottom: 16px;
}
.crumb .link {
  cursor: pointer;
  color: var(--mall-primary);
}
.crumb .sep {
  margin: 0 6px;
}
.box {
  background: var(--mall-card);
  border-radius: var(--mall-radius);
  padding: 18px 20px;
  box-shadow: var(--mall-shadow);
  margin-bottom: 16px;
}
.box-title {
  font-size: 15px;
  font-weight: 700;
  font-family: var(--mall-font-serif);
  color: var(--mall-text);
  margin-bottom: 14px;
}
.status-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.status-text {
  font-size: 20px;
  font-weight: 700;
  color: var(--mall-primary);
}
.status-desc {
  font-size: 13px;
  color: var(--mall-text-light);
  margin-top: 4px;
}
.countdown {
  font-weight: 700;
  color: var(--mall-price);
  font-variant-numeric: tabular-nums;
  margin: 0 2px;
}
.countdown.urgent {
  color: var(--mall-primary);
}
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px 24px;
  font-size: 14px;
  color: var(--mall-text);
}
.info-grid .full {
  grid-column: 1 / -1;
}
.info-grid .lbl {
  display: inline-block;
  width: 70px;
  color: var(--mall-text-light);
}
.goods-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.goods-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 0;
  border-bottom: 1px dashed var(--mall-border);
}
.goods-row:last-child {
  border-bottom: none;
}
.g-img {
  width: 64px;
  height: 64px;
  border-radius: var(--mall-radius-sm);
  background: var(--mall-primary-soft);
  overflow: hidden;
  flex: 0 0 64px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.g-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.img-ph {
  font-size: 26px;
  font-weight: 700;
  color: var(--mall-text-light);
}
.g-info {
  flex: 1;
  min-width: 0;
}
.g-name {
  font-size: 14px;
  color: var(--mall-text);
  margin-bottom: 4px;
}
.g-spec {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-bottom: 2px;
}
.g-sn {
  font-size: 12px;
  color: var(--mall-text-light);
}
.g-price,
.g-sub {
  font-size: 14px;
  color: var(--mall-price);
  width: 90px;
  text-align: right;
}
.g-act {
  margin-left: 8px;
  flex: 0 0 auto;
}
.g-reviewed {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-left: 8px;
}
.g-qty {
  font-size: 14px;
  color: var(--mall-text-light);
  width: 50px;
  text-align: center;
}
.settle-row {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: var(--mall-text);
  padding: 6px 0;
}
.settle-row.total {
  border-top: 1px dashed var(--mall-border);
  margin-top: 6px;
  padding-top: 12px;
}
.pay-num {
  font-size: 20px;
  font-weight: 700;
  color: var(--mall-price);
}
</style>
