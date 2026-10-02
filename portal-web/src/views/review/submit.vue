<template>
  <div class="page">
    <div class="crumb">
      <span class="link" @click="activeItem ? backToList() : router.back()">
        {{ activeItem ? '返回清单' : '返回' }}
      </span>
      <span class="sep">/</span>
      <span>{{ activeItem ? '发表评价' : (mode === 'order' ? '订单评价' : '发表评价') }}</span>
    </div>

    <!-- 整单模式：待评价清单（从订单列表页带 orderId 进入，无需进详情） -->
    <template v-if="mode === 'order' && !activeItem">
      <el-card shadow="never" class="card" v-loading="detailLoading">
        <div class="list-title">待评价商品</div>
        <div v-if="!detailLoading && pendingItems.length === 0" class="empty-tip">
          该订单的商品都已评价啦~
        </div>
        <div v-for="it in pendingItems" :key="it.id" class="pending-row">
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
            <div v-if="it.spData" class="g-spec">{{ formatSpecSafe(it.spData) }}</div>
          </div>
          <el-button type="primary" size="small" @click="pickItem(it)">评价</el-button>
        </div>
      </el-card>
    </template>

    <!-- 评价表单（单品模式 / 整单模式已选商品） -->
    <template v-else>
      <el-card shadow="never" class="card">
        <!-- 被评价商品快照 -->
        <div class="goods">
          <PicBox
            class="g-img"
            :pic="productPic"
            :name="productName"
            :ratio="1"
            :scale="1"
            ph-class="img-ph"
          />
          <div class="g-info">
            <div class="g-name">{{ productName }}</div>
            <div v-if="spec" class="g-spec">{{ formatSpecSafe(spec) }}</div>
          </div>
        </div>

        <el-divider />

        <div class="row">
          <span class="row-label">评分</span>
          <el-rate v-model="star" :max="5" />
          <span class="row-hint">{{ starText }}</span>
        </div>

        <div class="row col">
          <span class="row-label">评价内容</span>
          <el-input
            v-model="content"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="说说这件商品的使用感受吧~"
          />
        </div>

        <div class="row col">
          <span class="row-label">晒单图片</span>
          <el-upload
            v-model:file-list="fileList"
            list-type="picture-card"
            :http-request="handleUpload"
            :before-upload="beforeUpload"
            :on-remove="handleRemove"
            :limit="6"
            accept="image/*"
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </div>

        <div class="row">
          <span class="row-label">匿名评价</span>
          <el-switch v-model="anonymous" />
          <span class="row-hint">开启后将显示为「匿名用户」</span>
        </div>

        <div class="actions">
          <el-button v-if="mode === 'order' && activeItem" @click="backToList">返回清单</el-button>
          <el-button @click="activeItem ? backToList() : router.back()">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submit">提交评价</el-button>
        </div>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import type { UploadRequestOptions, UploadUserFile } from 'element-plus'
import { submitComment } from '@/apis/comment'
import { uploadImage } from '@/apis/upload'
import { getOrderDetail } from '@/apis/order'
import { formatSpec } from '@/utils/spec'
import type { OrderItem } from '@/types/order'
import PicBox from '@/components/PicBox.vue'

const route = useRoute()
const router = useRouter()

const orderItemIdFromQuery = Number(route.query.orderItemId)
const orderIdFromQuery = Number(route.query.orderId)

// 单品模式（带 orderItemId，来自商品详情/订单详情）：直接评一项
// 整单模式（带 orderId，来自订单列表）：先列待评项，再逐项评
const mode = computed<'single' | 'order'>(() =>
  orderItemIdFromQuery ? 'single' : 'order'
)

// 单品模式：商品快照来自路由 query
const productName = ref<string>((route.query.productName as string) || '商品')
const productPic = ref<string>((route.query.productPic as string) || '')
const spec = ref<string>((route.query.spec as string) || '')

// 整单模式：待评价清单 + 当前选中项
const detailLoading = ref(false)
const pendingItems = ref<OrderItem[]>([])
const activeItem = ref<OrderItem | null>(null)

const currentOrderItemId = computed(() =>
  mode.value === 'single' ? orderItemIdFromQuery : (activeItem.value?.id ?? 0)
)

function formatSpecSafe(s?: string) {
  if (!s) return ''
  try {
    return formatSpec(s)
  } catch {
    return ''
  }
}

const star = ref(5)
const content = ref('')
const anonymous = ref(false)
const fileList = ref<UploadUserFile[]>([])
const uploadedUrls = ref<string[]>([])
const submitting = ref(false)

const starTextMap = ['很差', '较差', '一般', '满意', '非常满意']
const starText = computed(() => starTextMap[(star.value || 1) - 1] || '')

// 整单模式：拉订单详情，筛出未评价项
async function loadPending() {
  if (mode.value !== 'order' || !orderIdFromQuery) return
  detailLoading.value = true
  try {
    const detail = await getOrderDetail(orderIdFromQuery)
    pendingItems.value = (detail.items || []).filter((it) => it.commentStatus !== 1)
  } catch (e) {
    console.error('加载订单待评项失败', e)
    ElMessage.error('加载订单失败')
  } finally {
    detailLoading.value = false
  }
}

// 从清单中选一项进入填写
function pickItem(it: OrderItem) {
  activeItem.value = it
  productName.value = it.productName || '商品'
  productPic.value = it.productPic || ''
  spec.value = it.spData || ''
  star.value = 5
  content.value = ''
  anonymous.value = false
  fileList.value = []
  uploadedUrls.value = []
}

function backToList() {
  activeItem.value = null
}

function beforeUpload(file: File) {
  if (!file.type.startsWith('image/')) {
    ElMessage.error('只能上传图片文件')
    return false
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('单张图片不能超过 5MB')
    return false
  }
  return true
}

async function handleUpload(option: UploadRequestOptions) {
  try {
    const url = await uploadImage(option.file as File)
    uploadedUrls.value.push(url)
    option.onSuccess(url)
    return url
  } catch (e) {
    const msg = e instanceof Error ? e.message : '上传失败'
    option.onError({
      status: 0,
      method: 'post',
      url: '',
      message: msg,
      name: 'UploadError',
    } as never)
    throw e
  }
}

function handleRemove(file: UploadUserFile) {
  const url = (file.response as string) || file.url || ''
  uploadedUrls.value = uploadedUrls.value.filter((u) => u !== url)
}

async function submit() {
  const oiId = currentOrderItemId.value
  if (!oiId) {
    ElMessage.error('缺少订单项信息')
    return
  }
  if (!content.value.trim() && uploadedUrls.value.length === 0) {
    ElMessage.warning('请填写评价内容或上传图片')
    return
  }
  submitting.value = true
  try {
    await submitComment({
      orderItemId: oiId,
      star: star.value,
      content: content.value.trim() || undefined,
      pics: uploadedUrls.value,
      anonymous: anonymous.value,
    })
    ElMessage.success('评价已提交，将在审核通过后公开展示')
    if (mode.value === 'single') {
      router.back()
    } else {
      // 整单模式：从清单移除已评项；若全部评完则提示并返回
      pendingItems.value = pendingItems.value.filter((it) => it.id !== oiId)
      activeItem.value = null
      if (pendingItems.value.length === 0) {
        ElMessage.success('该订单商品已全部评价')
        router.back()
      }
    }
  } catch (e) {
    console.error('提交评价失败', e)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  if (mode.value === 'order') loadPending()
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
.card {
  max-width: 720px;
  border-radius: var(--mall-radius);
}
.list-title {
  font-size: 15px;
  font-weight: 700;
  font-family: var(--mall-font-serif);
  color: var(--mall-text);
  margin-bottom: 12px;
}
.empty-tip {
  font-size: 14px;
  color: var(--mall-text-light);
  padding: 24px 0;
  text-align: center;
}
.pending-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 0;
  border-bottom: 1px dashed var(--mall-border);
}
.pending-row:last-child {
  border-bottom: none;
}
.goods {
  display: flex;
  align-items: center;
  gap: 14px;
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
}
.goods .g-info {
  margin-bottom: 4px;
}
.row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 18px 0;
}
.row.col {
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
}
.row-label {
  font-size: 14px;
  color: var(--mall-text);
  width: 72px;
  flex: 0 0 72px;
}
.row-hint {
  font-size: 12px;
  color: var(--mall-text-light);
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
}
</style>
