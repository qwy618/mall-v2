<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-bar">
        <span>售后管理</span>
        <el-button type="primary" plain @click="goOrder" v-if="backToOrder">返回订单</el-button>
      </div>
    </template>

    <!-- 筛选区 -->
    <el-form :inline="true" class="filter-bar" @submit.prevent>
      <el-form-item label="状态">
        <el-select v-model="filterStatus" placeholder="全部" clearable style="width: 150px" @change="handleSearch">
          <el-option :value="undefined" label="全部" />
          <el-option :value="0" label="待审核" />
          <el-option :value="1" label="待退货" />
          <el-option :value="2" label="已拒绝" />
          <el-option :value="3" label="已收货" />
          <el-option :value="4" label="已完成" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 主表格 -->
    <el-table :data="list" v-loading="loading" border>
      <el-table-column prop="id" label="售后ID" width="90" />
      <el-table-column prop="orderSn" label="订单号" min-width="190" />
      <el-table-column prop="memberId" label="会员ID" width="90" />
      <el-table-column label="退款金额" width="120">
        <template #default="{ row }">¥{{ formatMoney(row.returnAmount) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="RETURN_STATUS_TAG[row.status]">{{ RETURN_STATUS_TEXT[row.status] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="申请时间" min-width="180">
        <template #default="{ row }">{{ formatDateTime(row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="pageNum"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="handleSizeChange"
      @current-change="handleCurrentChange"
      style="margin-top: 16px; justify-content: flex-end"
    />

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="售后详情" size="600px" @open="onDrawerOpen">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="售后ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="订单号">{{ detail.orderSn }}</el-descriptions-item>
          <el-descriptions-item label="会员ID">{{ detail.memberId }}</el-descriptions-item>
          <el-descriptions-item label="退款金额">
            <span style="color: var(--mall-price); font-weight: 700">¥{{ formatMoney(detail.returnAmount) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="RETURN_STATUS_TAG[detail.status ?? 0]">{{ RETURN_STATUS_TEXT[detail.status ?? 0] }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="退货原因">{{ detail.reason || '—' }}</el-descriptions-item>
          <el-descriptions-item label="问题描述">{{ detail.description || '—' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.handleMan" label="处理人">{{ detail.handleMan }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.handleNote" label="处理备注">{{ detail.handleNote }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.companyAddress" label="退货地址">{{ detail.companyAddress }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.returnTrackingNo" label="退货物流单号">{{ detail.returnTrackingNo }}</el-descriptions-item>
          <el-descriptions-item label="申请时间">{{ formatDateTime(detail.createTime) }}</el-descriptions-item>
        </el-descriptions>

        <el-divider>退货商品</el-divider>
        <el-table :data="detailItems" border size="small">
          <el-table-column label="商品" min-width="160">
            <template #default="{ row }">
              <div class="good-cell">
                <img v-if="row.productPic" :src="row.productPic" class="good-img" alt="" />
                <span>{{ row.productName }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="quantity" label="退货数" width="80" />
          <el-table-column label="实付退款" width="110">
            <template #default="{ row }">¥{{ formatMoney(row.realAmount) }}</template>
          </el-table-column>
        </el-table>

        <el-divider v-if="detailProof.length">凭证图片</el-divider>
        <div v-if="detailProof.length" class="proof-imgs">
          <el-image
            v-for="(u, i) in detailProof"
            :key="i"
            :src="u"
            :preview-src-list="detailProof"
            :initial-index="i"
            class="proof-img"
            fit="cover"
          />
        </div>

        <!-- 操作按钮 -->
        <el-divider>操作</el-divider>
        <div class="actions">
          <el-button
            v-if="detail.status === 0"
            type="primary"
            :loading="acting"
            @click="openApprove"
          >同意退货</el-button>
          <el-button
            v-if="detail.status === 0"
            type="danger"
            :loading="acting"
            @click="openReject"
          >拒绝</el-button>
          <el-button
            v-if="detail.status === 1"
            type="success"
            :loading="acting"
            @click="handleReceive"
          >确认收货</el-button>
          <el-button
            v-if="detail.status === 3"
            type="warning"
            :loading="acting"
            @click="openComplete"
          >完成退款</el-button>
          <el-tag v-if="detail.status === 2 || detail.status === 4" type="info">
            {{ detail.status === 2 ? '已拒绝' : '退款已完成' }}
          </el-tag>
        </div>
      </template>
    </el-drawer>

    <!-- 同意弹窗（填退货地址） -->
    <el-dialog v-model="approveVisible" title="同意退货" width="460px">
      <el-form label-width="90px">
        <el-form-item label="退货地址" required>
          <el-input v-model="approveForm.companyAddress" type="textarea" :rows="2" placeholder="买家寄回的收货地址" />
        </el-form-item>
        <el-form-item label="处理备注">
          <el-input v-model="approveForm.handleNote" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approveVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitApprove">确定同意</el-button>
      </template>
    </el-dialog>

    <!-- 拒绝 / 完成退款弹窗 -->
    <el-dialog v-model="noteVisible" :title="noteTitle" width="460px">
      <el-form label-width="90px">
        <el-form-item :label="noteTitle + '备注'">
          <el-input v-model="noteForm.handleNote" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="noteVisible = false">取消</el-button>
        <el-button :type="noteIsReject ? 'danger' : 'warning'" :loading="acting" @click="submitNote">{{ noteIsReject ? '确定拒绝' : '确定退款' }}</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listReturnApplies,
  getReturnApplyDetail,
  approveReturn,
  rejectReturn,
  receiveReturn,
  completeReturn,
} from '@/apis/return'
import { RETURN_STATUS_TEXT, RETURN_STATUS_TAG, type ReturnApplyEntity, type ReturnItemDTO } from '@/types/return'
import { formatDateTime } from '@/utils/format'

const route = useRoute()
const router = useRouter()

// 列表状态
const list = ref<ReturnApplyEntity[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const filterStatus = ref<number | undefined>(undefined)

// 从订单页跳来时可带 status 预筛
const backToOrder = ref(false)
const initStatus = route.query.status
if (initStatus !== undefined) {
  const s = Number(initStatus)
  if (!Number.isNaN(s)) filterStatus.value = s
}

function formatMoney(v?: number): string {
  return (v ?? 0).toFixed(2)
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

async function loadData() {
  loading.value = true
  try {
    const data = await listReturnApplies({
      status: filterStatus.value,
      pageNum: pageNum.value,
      pageSize: pageSize.value,
    })
    list.value = data.list
    total.value = data.total
  } catch (error) {
    console.error('加载售后列表失败:', error)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pageNum.value = 1
  loadData()
}
function handleReset() {
  filterStatus.value = undefined
  pageNum.value = 1
  loadData()
}
function handleSizeChange(size: number) {
  pageSize.value = size
  pageNum.value = 1
  loadData()
}
function handleCurrentChange(page: number) {
  pageNum.value = page
  loadData()
}
function goOrder() {
  router.push('/order')
}

// 详情抽屉
const detailVisible = ref(false)
const detail = ref<ReturnApplyEntity | null>(null)
const acting = ref(false)
let currentId = 0

const detailItems = computed<ReturnItemDTO[]>(() => parseArray<ReturnItemDTO>(detail.value?.returnItems))
const detailProof = computed<string[]>(() => parseArray<string>(detail.value?.proofPics))

function openDetail(row: ReturnApplyEntity) {
  currentId = row.id ?? 0
  detailVisible.value = true
}
async function onDrawerOpen() {
  try {
    detail.value = await getReturnApplyDetail(currentId)
  } catch (error) {
    console.error('加载售后详情失败:', error)
  }
}

// 同意
const approveVisible = ref(false)
const approveForm = ref({ companyAddress: '', handleNote: '' })
function openApprove() {
  approveForm.value = { companyAddress: '', handleNote: '' }
  approveVisible.value = true
}
async function submitApprove() {
  if (!approveForm.value.companyAddress.trim()) {
    ElMessage.warning('请填写退货地址')
    return
  }
  acting.value = true
  try {
    await approveReturn(currentId, approveForm.value.handleNote, approveForm.value.companyAddress.trim())
    ElMessage.success('已同意退货')
    approveVisible.value = false
    loadData()
    onDrawerOpen()
  } catch (error) {
    console.error('同意失败:', error)
  } finally {
    acting.value = false
  }
}

// 拒绝 / 完成退款（共用备注弹窗）
const noteVisible = ref(false)
const noteIsReject = ref(false)
const noteTitle = ref('')
const noteForm = ref({ handleNote: '' })
function openReject() {
  noteIsReject.value = true
  noteTitle.value = '拒绝'
  noteForm.value = { handleNote: '' }
  noteVisible.value = true
}
function openComplete() {
  noteIsReject.value = false
  noteTitle.value = '完成退款'
  noteForm.value = { handleNote: '' }
  noteVisible.value = true
}
async function submitNote() {
  acting.value = true
  try {
    if (noteIsReject.value) {
      await rejectReturn(currentId, noteForm.value.handleNote)
      ElMessage.success('已拒绝')
    } else {
      await completeReturn(currentId, noteForm.value.handleNote)
      ElMessage.success('已确认退款完成')
    }
    noteVisible.value = false
    loadData()
    onDrawerOpen()
  } catch (error) {
    console.error('操作失败:', error)
  } finally {
    acting.value = false
  }
}

// 确认收货
async function handleReceive() {
  try {
    await ElMessageBox.confirm('确认已收到买家寄回的商品？', '确认收货', { type: 'warning' })
  } catch {
    return
  }
  acting.value = true
  try {
    await receiveReturn(currentId)
    ElMessage.success('已确认收货')
    loadData()
    onDrawerOpen()
  } catch (error) {
    console.error('确认收货失败:', error)
  } finally {
    acting.value = false
  }
}

// 初始化：若从订单页带 status 进来，标记可返回
if (route.path === '/return' && route.query.from === 'order') backToOrder.value = true

loadData()
</script>

<style scoped>
.header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.filter-bar {
  margin-bottom: 16px;
}
.good-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.good-img {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  object-fit: cover;
}
.proof-imgs {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.proof-img {
  width: 90px;
  height: 90px;
  border-radius: 6px;
  border: 1px solid var(--admin-border);
}
.actions {
  display: flex;
  gap: 12px;
  align-items: center;
}
</style>
