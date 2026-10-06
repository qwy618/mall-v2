<template>
  <div class="page" v-loading="loading">
    <div class="crumb">
      <span class="link" @click="router.push('/member')">个人中心</span>
      <span class="sep">/</span>
      <span>我的售后</span>
    </div>
    <h2 class="page-title">我的售后</h2>

    <div v-if="!loading && applies.length === 0" class="empty-wrap">
      <el-empty description="暂无售后申请" />
      <el-button text type="primary" @click="router.push('/order/list')">去我的订单 ›</el-button>
    </div>

    <div v-else class="apply-list">
      <div v-for="a in applies" :key="a.id" class="apply-card" @click="goDetail(a.id)">
        <div class="a-top">
          <span class="a-sn">售后单号：{{ a.id }} · 订单号：{{ a.orderSn }}</span>
          <el-tag :type="RETURN_STATUS_TAG[a.status ?? 0]" size="small">{{ RETURN_STATUS_TEXT[a.status ?? 0] }}</el-tag>
        </div>
        <div class="a-goods">
          <div v-for="(it, i) in parseItems(a.returnItems)" :key="i" class="a-good">
            <PicBox class="a-img" :pic="it.productPic" :name="it.productName" :ratio="1" :scale="1" ph-class="img-ph" />
            <div class="a-good-info">
              <div class="a-name">{{ it.productName }}</div>
              <div class="a-qty">退货 ×{{ it.quantity }}</div>
            </div>
            <div class="a-amt">￥{{ money(it.realAmount ?? 0) }}</div>
          </div>
        </div>
        <div class="a-foot">
          <div class="a-reason">原因：{{ a.reason || '—' }}</div>
          <div class="a-amount">退款金额 <span class="amt">￥{{ money(a.returnAmount) }}</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listReturns } from '@/apis/return'
import { RETURN_STATUS_TEXT, RETURN_STATUS_TAG, type ReturnApplyEntity, type ReturnItemDTO } from '@/types/return'
import PicBox from '@/components/PicBox.vue'

const router = useRouter()
const applies = ref<ReturnApplyEntity[]>([])
const loading = ref(false)

function money(n?: number) {
  return (Number(n) || 0).toFixed(2)
}
function parseItems(s?: string): ReturnItemDTO[] {
  if (!s) return []
  try {
    const v = JSON.parse(s)
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}

async function fetchList() {
  loading.value = true
  try {
    applies.value = await listReturns()
  } catch {
    applies.value = []
  } finally {
    loading.value = false
  }
}

function goDetail(id?: number) {
  if (id) router.push({ path: '/return/detail', query: { id } })
}

onMounted(fetchList)
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
.empty-wrap {
  text-align: center;
  padding: 40px 0;
}
.apply-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.apply-card {
  background: var(--mall-card);
  border-radius: var(--mall-radius);
  padding: 16px 18px;
  box-shadow: var(--mall-shadow);
  cursor: pointer;
  transition: box-shadow 0.2s;
}
.apply-card:hover {
  box-shadow: 0 6px 18px rgba(232, 117, 42, 0.16);
}
.a-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--mall-border);
}
.a-sn {
  font-size: 13px;
  color: var(--mall-text-light);
}
.a-goods {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 0;
}
.a-good {
  display: flex;
  align-items: center;
  gap: 12px;
}
.a-img {
  width: 54px;
  height: 54px;
  border-radius: var(--mall-radius-sm);
  background: var(--mall-primary-soft);
  overflow: hidden;
  flex: 0 0 54px;
}
.a-img :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.img-ph {
  font-size: 22px;
  font-weight: 700;
  color: var(--mall-text-light);
}
.a-good-info {
  flex: 1;
  min-width: 0;
}
.a-name {
  font-size: 14px;
  color: var(--mall-text);
}
.a-qty {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-top: 2px;
}
.a-amt {
  font-size: 14px;
  color: var(--mall-price);
}
.a-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 10px;
  border-top: 1px dashed var(--mall-border);
  font-size: 13px;
  color: var(--mall-text-light);
}
.a-amount .amt {
  font-size: 16px;
  font-weight: 700;
  color: var(--mall-price);
  margin-left: 4px;
}
</style>
