<template>
  <div class="page">
    <el-tabs v-model="active" class="mall-tabs">
      <el-tab-pane label="可领取" name="available">
        <div class="coupon-list">
          <div class="coupon-card" v-for="c in available" :key="c.id">
            <div class="c-left">
              <div class="c-name">{{ c.name }}</div>
              <div class="c-meta">有效期至 {{ fmt(c.endTime) }}</div>
              <div class="c-use">{{ useTypeText(c.useType) }}</div>
            </div>
            <div class="c-right">
              <div class="c-amount">￥<span>{{ c.amount }}</span></div>
              <div class="c-cond">{{ c.minPoint && c.minPoint > 0 ? '满' + c.minPoint + '可用' : '无门槛' }}</div>
            </div>
            <div class="c-circle left"></div>
            <div class="c-circle right"></div>
            <div class="c-action">
              <el-button
                type="primary"
                size="small"
                :disabled="soldOut(c)"
                :loading="receivingId === c.id"
                @click="receive(c.id)"
              >
                {{ soldOut(c) ? '已抢光' : '立即领取' }}
              </el-button>
            </div>
          </div>
          <el-empty v-if="!loadingAvailable && available.length === 0" description="暂无可领优惠券" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="我的券" name="mine">
        <div class="coupon-list">
          <div class="coupon-card" v-for="m in mine" :key="m.coupon.id">
            <div class="c-left">
              <div class="c-name">{{ m.coupon.name }}</div>
              <div class="c-meta">领取时间 {{ m.createTime || '-' }}</div>
              <div class="c-use">{{ useTypeText(m.coupon.useType) }}</div>
            </div>
            <div class="c-right">
              <div class="c-amount">￥<span>{{ m.coupon.amount }}</span></div>
              <div class="c-cond">{{ m.coupon.minPoint && m.coupon.minPoint > 0 ? '满' + m.coupon.minPoint + '可用' : '无门槛' }}</div>
            </div>
            <div class="c-circle left"></div>
            <div class="c-circle right"></div>
            <div class="c-action">
              <el-tag :type="statusTag(m.status)">{{ statusText(m.status) }}</el-tag>
            </div>
          </div>
          <el-empty v-if="!loadingMine && mine.length === 0" description="还没有领取优惠券" />
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listCoupons, receiveCoupon, myCoupons } from '@/apis/coupon'
import type { Coupon, MyCouponVO } from '@/types/coupon'

const active = ref('available')
const available = ref<Coupon[]>([])
const mine = ref<MyCouponVO[]>([])
const loadingAvailable = ref(false)
const loadingMine = ref(false)
const receivingId = ref<number | null>(null)

function soldOut(c: Coupon) {
  const pub = c.publishCount ?? 0
  const rec = c.receiveCount ?? 0
  return pub > 0 && rec >= pub
}

function fmt(t?: string) {
  return t ? t.replace('T', ' ').slice(0, 10) : '长期有效'
}

function useTypeText(useType?: number) {
  if (useType === 1) return '指定分类商品可用'
  if (useType === 2) return '指定商品可用'
  return '全场通用'
}

function statusText(s: number) {
  return s === 0 ? '未使用' : s === 1 ? '已使用' : '已过期'
}
function statusTag(s: number): 'success' | 'info' | 'warning' {
  return s === 0 ? 'success' : s === 1 ? 'info' : 'warning'
}

async function fetchAvailable() {
  loadingAvailable.value = true
  try {
    available.value = await listCoupons()
  } finally {
    loadingAvailable.value = false
  }
}

async function fetchMine() {
  loadingMine.value = true
  try {
    mine.value = await myCoupons()
  } finally {
    loadingMine.value = false
  }
}

async function receive(couponId: number) {
  receivingId.value = couponId
  try {
    await receiveCoupon(couponId)
    ElMessage.success('领取成功')
    fetchAvailable()
  } finally {
    receivingId.value = null
  }
}

onMounted(() => {
  fetchAvailable()
  fetchMine()
})
</script>

<style scoped>
.page {
  padding: 20px 24px 32px;
  background: var(--mall-bg);
  min-height: calc(100vh - 60px);
}
.coupon-list {
  display: flex;
  flex-direction: column;
}
.coupon-card {
  position: relative;
  display: flex;
  align-items: center;
  background: var(--mall-card);
  border-radius: var(--mall-radius);
  margin-bottom: 16px;
  padding: 20px;
  box-shadow: var(--mall-shadow);
}
.c-left {
  flex: 1;
  min-width: 0;
}
.c-name {
  font-size: 16px;
  color: var(--mall-text);
  font-weight: 500;
  margin-bottom: 8px;
}
.c-meta {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-bottom: 4px;
}
.c-use {
  font-size: 12px;
  color: var(--mall-text-light);
}
.c-right {
  width: 120px;
  text-align: center;
  border-left: 1px dashed var(--mall-border);
  padding-left: 16px;
  margin-left: 16px;
}
.c-amount {
  color: var(--mall-price);
  font-size: 16px;
  font-weight: 600;
}
.c-amount span {
  font-size: 30px;
}
.c-cond {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-top: 4px;
}
.c-action {
  width: 96px;
  text-align: center;
  margin-left: 16px;
}
.c-circle {
  position: absolute;
  width: 14px;
  height: 14px;
  background: var(--mall-bg);
  border-radius: 50%;
  top: 50%;
  transform: translateY(-50%);
}
.c-circle.left {
  left: -7px;
}
.c-circle.right {
  right: -7px;
}
</style>
