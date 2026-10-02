<template>
  <div class="page" v-loading="loading">
    <div class="crumb">
      <span class="link" @click="router.push('/return/list')">我的售后</span>
      <span class="sep">/</span>
      <span>售后详情</span>
    </div>
    <h2 class="page-title">售后详情</h2>

    <el-empty v-if="!loading && !apply" description="申请不存在或参数有误" />

    <template v-if="apply">
      <!-- 状态卡片 -->
      <div class="box status-box" :class="statusClass(apply.status ?? 0)">
        <div>
          <div class="status-text">{{ RETURN_STATUS_TEXT[apply.status ?? 0] }}</div>
          <div class="status-desc">{{ statusDesc(apply.status ?? 0) }}</div>
        </div>
        <div class="status-amount">
          <span class="lbl">退款金额</span>
          <span class="num">￥{{ money(apply.returnAmount) }}</span>
        </div>
      </div>

      <!-- 退货商品 -->
      <div class="box">
        <div class="box-title">退货商品</div>
        <div class="goods-list">
          <div v-for="(it, i) in items" :key="i" class="goods-row">
            <PicBox class="g-img" :pic="it.productPic" :name="it.productName" :ratio="1" :scale="1" ph-class="img-ph" />
            <div class="g-info">
              <div class="g-name">{{ it.productName }}</div>
              <div class="g-qty">退货数量 ×{{ it.quantity }}</div>
            </div>
            <div class="g-amt">￥{{ money(it.realAmount ?? 0) }}</div>
          </div>
        </div>
      </div>

      <!-- 退货地址（已同意后显示） -->
      <div v-if="(apply.status ?? 0) >= 1 && apply.companyAddress" class="box address-box">
        <div class="box-title">退货地址</div>
        <div class="addr">{{ apply.companyAddress }}</div>
        <el-button
          v-if="apply.status === 1 && !apply.returnTrackingNo"
          type="primary"
          size="small"
          :loading="shipping"
          @click="shipDialog = true"
        >填写退货物流</el-button>
        <div v-if="apply.returnTrackingNo" class="tracking">
          退货物流单号：<span class="tk">{{ apply.returnTrackingNo }}</span>（已寄出，等待商家收货）
        </div>
      </div>

      <!-- 申请信息 -->
      <div class="box">
        <div class="box-title">申请信息</div>
        <div class="info-grid">
          <div><span class="lbl">售后单号</span>{{ apply.id }}</div>
          <div><span class="lbl">关联订单</span>{{ apply.orderSn }}</div>
          <div><span class="lbl">退货原因</span>{{ apply.reason || '—' }}</div>
          <div v-if="apply.handleMan"><span class="lbl">处理人</span>{{ apply.handleMan }}</div>
          <div class="full"><span class="lbl">问题描述</span>{{ apply.description || '—' }}</div>
          <div v-if="apply.handleNote"><span class="lbl">处理备注</span>{{ apply.handleNote }}</div>
          <div><span class="lbl">申请时间</span>{{ fmtTime(apply.createTime) }}</div>
        </div>
        <div v-if="proof.length" class="proof">
          <div class="lbl">凭证图片</div>
          <div class="proof-imgs">
            <img v-for="(u, i) in proof" :key="i" :src="u" class="proof-img" alt="凭证" />
          </div>
        </div>
      </div>
    </template>

    <!-- 填写物流弹窗 -->
    <el-dialog v-model="shipDialog" title="填写退货物流" width="420px">
      <el-form label-width="84px">
        <el-form-item label="物流单号" required>
          <el-input v-model="trackingNo" placeholder="请输入退货快递单号" maxlength="64" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shipDialog = false">取消</el-button>
        <el-button type="primary" :loading="shipping" @click="submitShip">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getReturnDetail, shipBackReturn } from '@/apis/return'
import { RETURN_STATUS_TEXT, type ReturnApplyEntity, type ReturnItemDTO } from '@/types/return'
import PicBox from '@/components/PicBox.vue'

const route = useRoute()
const router = useRouter()

const apply = ref<ReturnApplyEntity | null>(null)
const loading = ref(false)
const shipping = ref(false)
const shipDialog = ref(false)
const trackingNo = ref('')

function money(n?: number) {
  return (Number(n) || 0).toFixed(2)
}
function fmtTime(t?: string) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}
function parseArray<T>(s?: string): T[] {
  if (!s) return []
  try {
    const v = JSON.parse(s)
    return Array.isArray(v) ? v : []
  } catch {
    return []
  }
}
const items = computed<ReturnItemDTO[]>(() => parseArray<ReturnItemDTO>(apply.value?.returnItems))
// proofPics 在 apply 中存的是 JSON 字符串，解析为图片数组
const proof = computed<string[]>(() => parseArray<string>(apply.value?.proofPics))

function statusClass(s: number) {
  return s === 4 ? 'is-done' : s === 2 ? 'is-rejected' : ''
}
function statusDesc(s: number) {
  return [
    '已提交，请等待商家审核',
    '商家已同意，请按退货地址寄回商品并填写物流单号',
    '商家已拒绝本次售后申请',
    '商家已收到退货，正在处理退款',
    '退款已完成',
    '售后已关闭',
  ][s] ?? ''
}

async function fetchDetail() {
  const id = Number(route.query.id)
  if (!id) return
  loading.value = true
  try {
    apply.value = await getReturnDetail(id)
  } catch {
    apply.value = null
  } finally {
    loading.value = false
  }
}

async function submitShip() {
  if (!trackingNo.value.trim()) {
    ElMessage.warning('请输入物流单号')
    return
  }
  if (!apply.value?.id) return
  shipping.value = true
  try {
    await shipBackReturn(apply.value.id, trackingNo.value.trim())
    ElMessage.success('物流信息已提交')
    shipDialog.value = false
    fetchDetail()
  } catch (e: any) {
    ElMessage.error(e?.message || '提交失败')
  } finally {
    shipping.value = false
  }
}

onMounted(fetchDetail)
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
.status-box.is-done {
  background: linear-gradient(135deg, #f3f7f0, #fffdfb);
}
.status-box.is-rejected {
  background: linear-gradient(135deg, #fdf2f0, #fffdfb);
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
.status-amount {
  text-align: right;
}
.status-amount .lbl {
  display: block;
  font-size: 12px;
  color: var(--mall-text-light);
}
.status-amount .num {
  font-size: 22px;
  font-weight: 700;
  color: var(--mall-price);
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
}
.g-img :deep(img) {
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
}
.g-qty {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-top: 2px;
}
.g-amt {
  font-size: 14px;
  color: var(--mall-price);
}
.address-box .addr {
  font-size: 14px;
  color: var(--mall-text);
  line-height: 1.6;
  background: var(--mall-primary-soft);
  border-radius: var(--mall-radius-sm);
  padding: 10px 12px;
  margin-bottom: 12px;
}
.tracking {
  font-size: 13px;
  color: var(--mall-text-regular);
}
.tracking .tk {
  color: var(--mall-primary);
  font-weight: 600;
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
.proof {
  margin-top: 14px;
}
.proof .lbl {
  font-size: 14px;
  color: var(--mall-text-light);
  margin-bottom: 8px;
}
.proof-imgs {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.proof-img {
  width: 88px;
  height: 88px;
  border-radius: var(--mall-radius-sm);
  object-fit: cover;
  border: 1px solid var(--mall-border);
}
</style>
