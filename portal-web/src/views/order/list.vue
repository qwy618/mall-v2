<template>
  <div class="page">
    <div class="head">
      <h2 class="title">我的订单</h2>
    </div>

    <el-tabs v-model="activeStatus" class="mall-tabs" @tab-change="onTabChange">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane label="待支付" name="0" />
      <el-tab-pane label="待发货" name="1" />
      <el-tab-pane label="待收货" name="2" />
      <el-tab-pane label="已完成" name="3" />
      <el-tab-pane label="已取消" name="4" />
      <el-tab-pane label="已失效" name="5" />
    </el-tabs>

    <div v-loading="loading" class="order-list">
      <div v-for="o in orders" :key="o.id" class="order-card" @click="goDetail(o.id)">
        <div class="o-top">
          <span class="o-sn">订单号：{{ o.orderSn }}</span>
          <el-tag :type="statusTag(o.status)" size="small">{{ statusText(o.status) }}</el-tag>
        </div>
        <div class="o-body">
          <div class="o-amount">
            <span class="amt-label">实付</span>
            <span class="amt-num">￥{{ money(o.payAmount ?? o.totalAmount) }}</span>
          </div>
          <div class="o-addr">
            {{ o.receiverName }} {{ o.receiverPhone }}<br />
            {{ o.receiverProvince }}{{ o.receiverCity }}{{ o.receiverDistrict }} {{ o.receiverDetailAddress }}
          </div>
          <div class="o-time">
            {{ fmtTime(o.createTime) }}
            <span
              v-if="o.status === 0 && remainingMsOf(o) > 0"
              class="countdown"
              :class="{ urgent: isUrgentOf(o) }"
            >剩 {{ countdownOf(o) }}</span>
            <span v-else-if="o.status === 0 && remainingMsOf(o) <= 0" class="countdown urgent">已超时</span>
          </div>
        </div>
        <div class="o-foot">
          <el-button
            v-if="o.status === 0"
            type="primary"
            size="small"
            :loading="actingId === o.id"
            :disabled="remainingMsOf(o) <= 0"
            @click.stop="pay(o)"
          >去支付</el-button>
          <el-button
            v-if="o.status === 0"
            size="small"
            :loading="actingId === o.id"
            @click.stop="cancel(o)"
          >取消订单</el-button>
          <el-button
            v-if="o.status === 2"
            type="primary"
            size="small"
            :loading="actingId === o.id"
            @click.stop="confirm(o)"
          >确认收货</el-button>
          <el-button
            v-if="o.status === 3"
            type="primary"
            size="small"
            @click.stop="goReview(o.id)"
          >评价</el-button>
          <el-button
            v-if="o.status === 3"
            size="small"
            @click.stop="goReturn(o.id)"
          >申请售后</el-button>
          <el-button size="small" text @click.stop="goDetail(o.id)">查看详情</el-button>
        </div>
      </div>
      <el-empty v-if="!loading && orders.length === 0" description="还没有相关订单" />
    </div>

    <div class="pager">
      <el-pagination
        layout="prev, pager, next, total"
        :total="total"
        :current-page="pageNum"
        :page-size="pageSize"
        @current-change="onPageChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listOrders, payOrder, cancelOrder, confirmReceived } from '@/apis/order'
import { ORDER_PAY_TIMEOUT_MS } from '@/types/order'
import type { Order } from '@/types/order'

const router = useRouter()
const route = useRoute()

const activeStatus = ref<string>('all')
const orders = ref<Order[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const actingId = ref<number | null>(null)

function money(n?: number) {
  return (Number(n) || 0).toFixed(2)
}

function fmtTime(t?: string) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}

// 30 分钟支付倒计时（基于 createTime + ORDER_PAY_TIMEOUT_MS）
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | undefined

function formatRemaining(ms: number) {
  const total = Math.floor(ms / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)}`
}

function remainingMsOf(o: Order) {
  if (o.status !== 0 || !o.createTime) return 0
  const t = new Date(o.createTime.replace(' ', 'T')).getTime()
  if (Number.isNaN(t)) return 0
  return Math.max(0, t + ORDER_PAY_TIMEOUT_MS - now.value)
}

function countdownOf(o: Order) {
  return formatRemaining(remainingMsOf(o))
}

function isUrgentOf(o: Order) {
  const r = remainingMsOf(o)
  return r > 0 && r <= 5 * 60 * 1000
}

function statusText(s: number) {
  return ['待支付', '待发货', '待收货', '已完成', '已取消', '已失效'][s] ?? '未知'
}
function statusTag(s: number): 'warning' | 'primary' | 'success' | 'info' {
  if (s === 0) return 'warning'
  if (s === 1) return 'primary'
  if (s === 2) return 'primary'
  if (s === 3) return 'success'
  return 'info'
}

async function fetchList() {
  loading.value = true
  try {
    const params: { status?: number; pageNum: number; pageSize: number } = {
      pageNum: pageNum.value,
      pageSize: pageSize.value,
    }
    if (activeStatus.value !== 'all') params.status = Number(activeStatus.value)
    const data = await listOrders(params)
    orders.value = data.list
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function onTabChange() {
  pageNum.value = 1
  fetchList()
}

function onPageChange(p: number) {
  pageNum.value = p
  fetchList()
}

function goDetail(id?: number) {
  if (id) router.push({ path: '/order/detail', query: { orderId: id } })
}

// 已完成订单：直达整单评价（带 orderId，由评价页拉取待评项，无需进详情）
function goReview(orderId?: number) {
  if (orderId) router.push({ path: '/review/submit', query: { orderId } })
}

// 已完成订单：申请售后（带 orderId，由申请页勾选退货商品行）
function goReturn(orderId?: number) {
  if (orderId) router.push({ path: '/return/apply', query: { orderId } })
}

async function pay(o: Order) {
  actingId.value = o.id
  try {
    await payOrder(o.id)
    ElMessage.success('支付成功')
    fetchList()
  } finally {
    actingId.value = null
  }
}

async function cancel(o: Order) {
  try {
    await ElMessageBox.confirm('确定取消该订单？取消后将恢复库存', '提示', { type: 'warning' })
  } catch {
    return
  }
  actingId.value = o.id
  try {
    await cancelOrder(o.id)
    ElMessage.success('订单已取消')
    fetchList()
  } finally {
    actingId.value = null
  }
}

async function confirm(o: Order) {
  actingId.value = o.id
  try {
    await confirmReceived(o.id)
    ElMessage.success('已确认收货')
    fetchList()
  } finally {
    actingId.value = null
  }
}

onMounted(() => {
  const q = route.query.status
  if (q !== undefined) activeStatus.value = String(q)
  fetchList()
  timer = setInterval(() => {
    now.value = Date.now()
  }, 1000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.page {
  padding: 20px 24px 40px;
  background: var(--mall-bg);
  min-height: calc(100vh - 60px);
}
.head {
  margin-bottom: 8px;
}
.title {
  font-size: 20px;
  font-family: var(--mall-font-serif);
  color: var(--mall-text);
  margin: 0;
}
.order-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 120px;
}
.order-card {
  background: var(--mall-card);
  border-radius: var(--mall-radius);
  padding: 16px 18px;
  box-shadow: var(--mall-shadow);
  cursor: pointer;
  transition: box-shadow 0.2s;
}
.order-card:hover {
  box-shadow: 0 6px 18px rgba(232, 117, 42, 0.16);
}
.o-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--mall-border);
}
.o-sn {
  font-size: 13px;
  color: var(--mall-text-light);
}
.o-body {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 0;
}
.o-amount {
  display: flex;
  flex-direction: column;
}
.amt-label {
  font-size: 12px;
  color: var(--mall-text-light);
}
.amt-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--mall-price);
}
.o-addr {
  flex: 1;
  font-size: 13px;
  color: var(--mall-text);
  line-height: 1.6;
}
.o-time {
  font-size: 12px;
  color: var(--mall-text-light);
}
.countdown {
  font-weight: 700;
  color: var(--mall-price);
  font-variant-numeric: tabular-nums;
  margin-left: 8px;
}
.countdown.urgent {
  color: var(--mall-primary);
}
.o-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--mall-border);
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
