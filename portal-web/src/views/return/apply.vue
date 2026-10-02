<template>
  <div class="page" v-loading="loading">
    <div class="crumb">
      <span class="link" @click="router.push('/order/list')">我的订单</span>
      <span class="sep">/</span>
      <span>申请售后</span>
    </div>
    <h2 class="page-title">申请售后</h2>

    <el-empty v-if="!loading && !detail" description="订单不存在或参数有误" />

    <template v-if="detail">
      <!-- 商品清单：逐行选择退货数量 -->
      <div class="box">
        <div class="box-title">选择退货商品</div>
        <div class="goods-list">
          <div v-for="it in detail.items" :key="it.id" class="goods-row">
            <PicBox class="g-img" :pic="it.productPic" :name="it.productName" :ratio="1" :scale="1" ph-class="img-ph" />
            <div class="g-info">
              <div class="g-name">{{ it.productName }}</div>
              <div v-if="it.spData" class="g-spec">{{ formatSpec(it.spData) }}</div>
              <div class="g-sn">SKU：{{ it.skuCode }}</div>
              <div class="g-real">实付单价：￥{{ money(it.realAmount ?? 0) }}</div>
            </div>
            <div class="g-qty">
              <span class="qty-label">退货数量</span>
              <el-input-number
                v-model="returnQty[it.id]"
                :min="0"
                :max="it.quantity"
                :step="1"
                size="small"
                @change="recalc"
              />
              <span class="qty-max">/ 共 {{ it.quantity }} 件</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 退货信息 -->
      <div class="box">
        <div class="box-title">退货信息</div>
        <el-form label-width="84px" label-position="left">
          <el-form-item label="退货原因" required>
            <el-select v-model="reason" placeholder="请选择" style="width: 240px">
              <el-option v-for="r in RETURN_REASONS" :key="r" :label="r" :value="r" />
            </el-select>
          </el-form-item>
          <el-form-item label="问题描述">
            <el-input
              v-model="description"
              type="textarea"
              :rows="3"
              maxlength="500"
              show-word-limit
              placeholder="补充说明（选填）"
            />
          </el-form-item>
          <el-form-item label="凭证图片">
            <el-upload
              list-type="picture-card"
              :http-request="uploadProof"
              :before-upload="beforeImg"
              :on-remove="removeProof"
              :file-list="proofFileList"
              accept="image/*"
            >
              <el-icon><Plus /></el-icon>
            </el-upload>
            <span class="hint">最多 5 张，支持 jpg/png（选填）</span>
          </el-form-item>
        </el-form>
      </div>

      <!-- 底部汇总 + 提交 -->
      <div class="footer-bar">
        <div class="summary">
          预计退款：<span class="amt">￥{{ money(refundTotal) }}</span>
          <span class="summary-tip">（按实付金额分摊计算，仅退所选商品）</span>
        </div>
        <el-button type="primary" size="large" :loading="submitting" :disabled="!canSubmit" @click="submit">
          提交申请
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getOrderDetail } from '@/apis/order'
import { applyReturn } from '@/apis/return'
import { uploadImage } from '@/apis/upload'
import { formatSpec } from '@/utils/spec'
import { RETURN_REASONS, type ApplyItemParam } from '@/types/return'
import type { OrderDetailVO } from '@/types/order'
import PicBox from '@/components/PicBox.vue'

const route = useRoute()
const router = useRouter()

const detail = ref<OrderDetailVO | null>(null)
const loading = ref(false)
const submitting = ref(false)

// 每行退货数量（key = orderItemId）
const returnQty = reactive<Record<number, number>>({})
const reason = ref('')
const description = ref('')
const proofPics = ref<string[]>([])

// el-upload 文件列表（仅用于展示缩略图）
const proofFileList = ref<{ name: string; url: string; response?: string }[]>([])

function money(n?: number) {
  return (Number(n) || 0).toFixed(2)
}

// 预计退款 = Σ(实付单价 × 退货数量)
const refundTotal = computed(() => {
  if (!detail.value) return 0
  let sum = 0
  for (const it of detail.value.items) {
    const q = returnQty[it.id] || 0
    sum += Number(it.realAmount ?? 0) * q
  }
  return Math.round(sum * 100) / 100
})

const canSubmit = computed(() => {
  const hasQty = detail.value?.items.some((it) => (returnQty[it.id] || 0) > 0)
  return !!hasQty && !!reason.value
})

function recalc() {
  // 触发 computed 重新计算（returnQty 已是 reactive）
}

async function fetchDetail() {
  const orderId = Number(route.query.orderId)
  if (!orderId) return
  loading.value = true
  try {
    detail.value = await getOrderDetail(orderId)
    // 初始化退货数量（默认 0）
    detail.value?.items.forEach((it) => {
      if (returnQty[it.id] === undefined) returnQty[it.id] = 0
    })
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

// 凭证图上传
function beforeImg(file: File) {
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return false
  }
  if (proofPics.value.length >= 5) {
    ElMessage.warning('最多上传 5 张凭证图')
    return false
  }
  return true
}
async function uploadProof(option: any) {
  try {
    const url = await uploadImage(option.file)
    proofPics.value.push(url)
    option.onSuccess(url)
  } catch (e) {
    option.onError(e)
    ElMessage.error('图片上传失败')
  }
}
function removeProof(file: any) {
  const url = file.response || file.url
  if (url) proofPics.value = proofPics.value.filter((u) => u !== url)
}

async function submit() {
  if (!detail.value) return
  if (!canSubmit.value) {
    ElMessage.warning('请至少选择一件退货商品并填写原因')
    return
  }
  const items: ApplyItemParam[] = detail.value.items
    .filter((it) => (returnQty[it.id] || 0) > 0)
    .map((it) => ({ orderItemId: it.id, quantity: returnQty[it.id] }))

  submitting.value = true
  try {
    const id = await applyReturn({
      orderId: detail.value.order.id,
      items,
      reason: reason.value,
      description: description.value || undefined,
      proofPics: proofPics.value.length ? proofPics.value : undefined,
    })
    ElMessage.success('申请已提交，等待商家审核')
    router.replace({ path: '/return/detail', query: { id } })
  } catch (e: any) {
    ElMessage.error(e?.message || '提交失败')
  } finally {
    submitting.value = false
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
  margin-bottom: 4px;
}
.g-spec,
.g-sn,
.g-real {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-bottom: 2px;
}
.g-real {
  color: var(--mall-price);
}
.g-qty {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}
.qty-label {
  font-size: 12px;
  color: var(--mall-text-light);
}
.qty-max {
  font-size: 12px;
  color: var(--mall-text-light);
}
.hint {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-left: 12px;
}
.footer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--mall-card);
  border-radius: var(--mall-radius);
  padding: 16px 20px;
  box-shadow: var(--mall-shadow);
  position: sticky;
  bottom: 16px;
}
.summary {
  font-size: 14px;
  color: var(--mall-text);
}
.summary .amt {
  font-size: 22px;
  font-weight: 700;
  color: var(--mall-price);
}
.summary-tip {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-left: 8px;
}
</style>
