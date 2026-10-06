<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-bar">
        <span>优惠券列表</span>
        <div>
          <el-button @click="openMemberQuery">按会员查询</el-button>
          <el-button type="primary" @click="openCreate">新增优惠券</el-button>
        </div>
      </div>
    </template>

    <!-- 筛选区 -->
    <el-form :inline="true" class="filter-bar" @submit.prevent>
      <el-form-item label="关键词">
        <el-input
            v-model="keyword"
            placeholder="优惠券名称"
            clearable
            style="width: 180px"
            @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="适用类型">
        <el-select v-model="filterUseType" placeholder="全部" clearable style="width: 130px">
          <el-option :value="0" label="全场通用" />
          <el-option :value="1" label="指定分类" />
          <el-option :value="2" label="指定商品" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 主表格 -->
    <el-table :data="list" v-loading="loading" border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="优惠券名称" />
      <el-table-column label="面额" width="100">
        <template #default="{ row }">{{ amountText(row.amount) }}</template>
      </el-table-column>
      <el-table-column label="使用门槛" width="110">
        <template #default="{ row }">
          {{ row.minPoint && row.minPoint > 0 ? '满' + row.minPoint + '元' : '无门槛' }}
        </template>
      </el-table-column>
      <el-table-column label="适用" width="100">
        <template #default="{ row }">
          <el-tag :type="useTypeTagType(row.useType)">{{ useTypeText(row.useType) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="perLimit" label="限领/人" width="80" />
      <el-table-column prop="publishCount" label="发行量" width="80" />
      <el-table-column prop="receiveCount" label="已领" width="70" />
      <el-table-column prop="useCount" label="已用" width="70" />
      <el-table-column label="起止时间" width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ formatRange(row.startTime, row.endTime) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="couponStatus(row).type">{{ couponStatus(row).text }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
          <el-button size="small" link type="success" @click="openReceive(row)">模拟领取</el-button>
          <el-button size="small" link type="warning" @click="openHistories(row)">领取记录</el-button>
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

    <!-- 优惠券新增/编辑弹窗 -->
    <el-dialog
        v-model="dialogVisible"
        :title="dialogMode === 'edit' ? '编辑优惠券' : '新增优惠券'"
        width="640px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入优惠券名称" />
        </el-form-item>
        <el-form-item label="面额(元)" prop="amount">
          <el-input-number v-model="form.amount" :min="0.01" :precision="2" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="使用门槛(元)" prop="minPoint">
          <el-input-number v-model="form.minPoint" :min="0" :precision="2" :step="1" style="width: 100%" />
          <div class="form-hint">0 表示无门槛，任意金额可用</div>
        </el-form-item>
        <el-form-item label="适用类型" prop="useType">
          <el-select v-model="form.useType" style="width: 100%">
            <el-option :value="0" label="全场通用" />
            <el-option :value="1" label="指定分类" />
            <el-option :value="2" label="指定商品" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.useType === 1" label="适用分类" prop="categoryId">
          <el-select v-model="form.categoryId" placeholder="请选择分类" style="width: 100%">
            <el-option v-for="o in categoryOptions" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.useType === 2" label="适用商品ID" prop="productId">
          <el-input-number v-model="form.productId" :min="1" :precision="0" :step="1" style="width: 100%" />
          <div class="form-hint">填入商品 ID（product.id）</div>
        </el-form-item>
        <el-form-item label="每人限领" prop="perLimit">
          <el-input-number v-model="form.perLimit" :min="1" :precision="0" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="发行量" prop="publishCount">
          <el-input-number v-model="form.publishCount" :min="1" :precision="0" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效时间" prop="startTime">
          <el-date-picker
              v-model="form.startTime"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ss"
              placeholder="选择生效时间"
              style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="失效时间" prop="endTime">
          <el-date-picker
              v-model="form.endTime"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ss"
              placeholder="选择失效时间"
              style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注" prop="note">
          <el-input v-model="form.note" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 领取记录弹窗（某券的全部领取记录，分页） -->
    <el-dialog v-model="historyVisible" :title="`领取记录 - ${currentCouponName}`" width="820px">
      <el-table :data="historyList" v-loading="historyLoading" border size="small">
        <el-table-column prop="id" label="记录ID" width="80" />
        <el-table-column prop="memberId" label="会员ID" width="90" />
        <el-table-column prop="couponCode" label="券码" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="historyStatusTagType(row.status)">{{ historyStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="orderSn" label="关联订单" show-overflow-tooltip />
        <el-table-column prop="createTime" label="领取时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.createTime) }}</template>
        </el-table-column>
        <el-table-column prop="useTime" label="使用时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.useTime) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button
                v-if="row.status === 0"
                size="small"
                link
                type="primary"
                @click="openUse(row)"
            >核销</el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
          v-model:current-page="historyPageNum"
          v-model:page-size="historyPageSize"
          :total="historyTotal"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="handleHistorySizeChange"
          @current-change="handleHistoryCurrentChange"
          style="margin-top: 12px; justify-content: flex-end"
      />
    </el-dialog>

    <!-- 核销弹窗 -->
    <el-dialog v-model="useVisible" title="核销优惠券" width="460px">
      <el-form ref="useFormRef" :model="useForm" :rules="useRules" label-width="90px">
        <el-form-item label="记录ID">
          <span>{{ useForm.historyId }}</span>
        </el-form-item>
        <el-form-item label="订单ID" prop="orderId">
          <el-input-number v-model="useForm.orderId" :min="1" :precision="0" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="订单编号" prop="orderSn">
          <el-input v-model="useForm.orderSn" placeholder="请输入订单编号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="useVisible = false">取消</el-button>
        <el-button type="primary" :loading="useSubmitting" @click="submitUse">确定核销</el-button>
      </template>
    </el-dialog>

    <!-- 按会员查询弹窗 -->
    <el-dialog v-model="memberVisible" title="按会员查询领取记录" width="860px">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="会员ID">
          <el-input-number v-model="memberId" :min="1" :precision="0" :step="1" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="memberStatus" placeholder="全部" clearable style="width: 120px">
            <el-option :value="0" label="未使用" />
            <el-option :value="1" label="已使用" />
            <el-option :value="2" label="已过期" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadMemberHistory">查询</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="memberList" v-loading="memberLoading" border size="small">
        <el-table-column prop="id" label="记录ID" width="80" />
        <el-table-column prop="couponId" label="券ID" width="80" />
        <el-table-column prop="memberId" label="会员ID" width="90" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="historyStatusTagType(row.status)">{{ historyStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="orderSn" label="关联订单" show-overflow-tooltip />
        <el-table-column prop="createTime" label="领取时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.createTime) }}</template>
        </el-table-column>
        <el-table-column prop="useTime" label="使用时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.useTime) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import {
  listCoupon,
  getCouponDetail,
  createCoupon,
  updateCoupon,
  deleteCoupon,
  receiveCoupon,
  useCoupon,
  listCouponHistories,
  listCouponHistoryByMember,
  type CouponListParams,
} from '@/apis/coupon'
import type { Coupon, CouponParam, CouponHistory } from '@/types/coupon'
import { COUPON_USE_TYPE_TEXT, COUPON_HISTORY_STATUS_TEXT } from '@/types/coupon'
import { listCategory } from '@/apis/category'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { formatDateTime } from '@/utils/format'

// ==================== 列表状态 ====================
const list = ref<Coupon[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)

// ==================== 筛选条件 ====================
const keyword = ref('')
const filterUseType = ref<number | undefined>(undefined)

// ==================== 分类下拉（useType=1 时可选） ====================
const categoryOptions = ref<{ id: number; name: string }[]>([])

// ==================== 优惠券新增/编辑弹窗 ====================
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<CouponParam>({
  name: '',
  amount: 0,
  minPoint: 0,
  useType: 0,
  categoryId: undefined,
  productId: undefined,
  perLimit: 1,
  publishCount: 1,
  startTime: '',
  endTime: '',
  note: '',
})
const rules: FormRules<CouponParam> = {
  name: [{ required: true, message: '请输入优惠券名称', trigger: 'blur' }],
  amount: [{ required: true, type: 'number', min: 0.01, message: '面额必须大于 0', trigger: 'blur' }],
  perLimit: [{ required: true, type: 'number', min: 1, message: '每人限领至少 1 张', trigger: 'blur' }],
  publishCount: [{ required: true, type: 'number', min: 1, message: '发行量至少 1 张', trigger: 'blur' }],
}

// ==================== 领取记录弹窗 ====================
const historyVisible = ref(false)
const currentCouponId = ref<number | null>(null)
const currentCouponName = ref('')
const historyList = ref<CouponHistory[]>([])
const historyTotal = ref(0)
const historyPageNum = ref(1)
const historyPageSize = ref(10)
const historyLoading = ref(false)

// ==================== 核销弹窗 ====================
const useVisible = ref(false)
const useSubmitting = ref(false)
const useFormRef = ref<FormInstance>()
const useForm = reactive<{ historyId: number; orderId: number | undefined; orderSn: string }>({
  historyId: 0,
  orderId: undefined,
  orderSn: '',
})
const useRules: FormRules<typeof useForm> = {
  orderId: [{ required: true, type: 'number', min: 1, message: '请输入订单 ID', trigger: 'blur' }],
  orderSn: [{ required: true, message: '请输入订单编号', trigger: 'blur' }],
}

// ==================== 按会员查询弹窗 ====================
const memberVisible = ref(false)
const memberId = ref<number | undefined>(undefined)
const memberStatus = ref<number | undefined>(undefined)
const memberList = ref<CouponHistory[]>([])
const memberLoading = ref(false)

// ==================== 文案/格式化辅助 ====================
function useTypeText(useType: number): string {
  return COUPON_USE_TYPE_TEXT[useType] ?? '未知'
}
function useTypeTagType(useType: number): 'success' | 'warning' | 'info' {
  return useType === 0 ? 'success' : useType === 1 ? 'warning' : 'info'
}
function historyStatusText(status: number): string {
  return COUPON_HISTORY_STATUS_TEXT[status] ?? '未知'
}
function historyStatusTagType(status: number): 'success' | 'warning' | 'info' {
  return status === 0 ? 'warning' : status === 1 ? 'success' : 'info'
}
function amountText(amount?: number): string {
  return amount != null ? `¥${Number(amount).toFixed(2)}` : '-'
}
function formatRange(start?: string, end?: string): string {
  if (!start && !end) return '长期有效'
  return `${formatDateTime(start)} ~ ${formatDateTime(end)}`
}
function couponStatus(row: Coupon): { text: string; type: 'success' | 'info' | 'danger' } {
  if (!row.startTime || !row.endTime) return { text: '长期', type: 'success' }
  const now = Date.now()
  const s = new Date(row.startTime).getTime()
  const e = new Date(row.endTime).getTime()
  if (now < s) return { text: '未开始', type: 'info' }
  if (now > e) return { text: '已结束', type: 'danger' }
  return { text: '进行中', type: 'success' }
}

// ==================== 加载数据 ====================
async function loadData() {
  loading.value = true
  try {
    const params: CouponListParams = {
      pageNum: pageNum.value,
      pageSize: pageSize.value,
    }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (filterUseType.value !== undefined && filterUseType.value !== null) {
      params.useType = filterUseType.value
    }
    const data = await listCoupon(params)
    list.value = data.list
    total.value = data.total
  } catch (error) {
    console.error('加载优惠券列表失败:', error)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pageNum.value = 1
  loadData()
}
function handleReset() {
  keyword.value = ''
  filterUseType.value = undefined
  pageNum.value = 1
  loadData()
}

async function loadCategoryOptions() {
  try {
    const data = await listCategory(1, 100)
    categoryOptions.value = data.list.map((c) => ({ id: c.id, name: c.name }))
  } catch (error) {
    console.error('加载分类下拉失败:', error)
  }
}

// ==================== 分页事件 ====================
function handleSizeChange(size: number) {
  pageSize.value = size
  pageNum.value = 1
  loadData()
}
function handleCurrentChange(page: number) {
  pageNum.value = page
  loadData()
}

// ==================== 优惠券 新增/编辑 ====================
function openCreate() {
  dialogMode.value = 'create'
  editId.value = null
  formRef.value?.resetFields()
  Object.assign(form, {
    name: '',
    amount: 0,
    minPoint: 0,
    useType: 0,
    categoryId: undefined,
    productId: undefined,
    perLimit: 1,
    publishCount: 1,
    startTime: '',
    endTime: '',
    note: '',
  })
  dialogVisible.value = true
}

async function openEdit(row: Coupon) {
  dialogMode.value = 'edit'
  editId.value = row.id
  try {
    const data = await getCouponDetail(row.id)
    Object.assign(form, {
      name: data.name,
      amount: data.amount,
      minPoint: data.minPoint || 0,
      useType: data.useType,
      categoryId: data.categoryId,
      productId: data.productId,
      perLimit: data.perLimit,
      publishCount: data.publishCount,
      startTime: data.startTime || '',
      endTime: data.endTime || '',
      note: data.note || '',
    })
    dialogVisible.value = true
  } catch (error) {
    console.error('加载优惠券详情失败:', error)
  }
}

async function submitForm() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      // 按 useType 只带对应的关联字段，其余置 undefined（axios 序列化时自动省略）
      const payload: CouponParam = {
        name: form.name,
        amount: form.amount,
        minPoint: form.minPoint || 0,
        useType: form.useType,
        perLimit: form.perLimit,
        publishCount: form.publishCount,
        startTime: form.startTime || undefined,
        endTime: form.endTime || undefined,
        note: form.note || undefined,
      }
      if (form.useType === 1) payload.categoryId = form.categoryId
      if (form.useType === 2) payload.productId = form.productId
      if (dialogMode.value === 'create') {
        const id = await createCoupon(payload)
        ElMessage.success(`新增成功，ID=${id}`)
      } else {
        const affected = await updateCoupon(editId.value!, payload)
        ElMessage.success(`修改成功，影响 ${affected} 行`)
      }
      dialogVisible.value = false
      loadData()
    } catch (error) {
      console.error('提交优惠券失败:', error)
    } finally {
      submitting.value = false
    }
  })
}

async function handleDelete(row: Coupon) {
  try {
    await ElMessageBox.confirm(
      `确定删除优惠券「${row.name}」吗？此操作不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    const affected = await deleteCoupon(row.id)
    ElMessage.success(`删除成功，影响 ${affected} 行`)
    loadData()
  } catch (error) {
    console.error('删除优惠券失败:', error)
  }
}

// ==================== 模拟领取 ====================
async function openReceive(row: Coupon) {
  try {
    const { value } = await ElMessageBox.prompt('请输入会员 ID（阶段8 由运营后台模拟领取）', '模拟领取', {
      inputType: 'number',
      confirmButtonText: '领取',
      cancelButtonText: '取消',
      inputValidator: (v) => (v && Number(v) > 0) || '会员 ID 必须大于 0',
    })
    const memberId = Number(value)
    const id = await receiveCoupon(row.id, memberId)
    ElMessage.success(`模拟领取成功，领取记录 ID=${id}`)
    loadData()
  } catch (error) {
    // 用户取消或后端返回业务错误（已领完/超限领）由拦截器提示，这里仅吞掉取消
    if (error !== 'cancel' && error !== 'close') console.error('模拟领取失败:', error)
  }
}

// ==================== 领取记录（分页） ====================
async function openHistories(row: Coupon) {
  currentCouponId.value = row.id
  currentCouponName.value = row.name
  historyPageNum.value = 1
  historyVisible.value = true
  await loadHistories()
}

async function loadHistories() {
  if (!currentCouponId.value) return
  historyLoading.value = true
  try {
    const data = await listCouponHistories(
      currentCouponId.value,
      historyPageNum.value,
      historyPageSize.value
    )
    historyList.value = data.list
    historyTotal.value = data.total
  } catch (error) {
    console.error('加载领取记录失败:', error)
  } finally {
    historyLoading.value = false
  }
}

function handleHistorySizeChange(size: number) {
  historyPageSize.value = size
  historyPageNum.value = 1
  loadHistories()
}
function handleHistoryCurrentChange(page: number) {
  historyPageNum.value = page
  loadHistories()
}

// ==================== 核销 ====================
function openUse(row: CouponHistory) {
  useForm.historyId = row.id
  useForm.orderId = undefined
  useForm.orderSn = ''
  useVisible.value = true
}

async function submitUse() {
  if (!useFormRef.value) return
  await useFormRef.value.validate(async (valid) => {
    if (!valid) return
    useSubmitting.value = true
    try {
      await useCoupon(useForm.historyId, Number(useForm.orderId), useForm.orderSn)
      ElMessage.success('核销成功')
      useVisible.value = false
      await loadHistories()
    } catch (error) {
      console.error('核销失败:', error)
    } finally {
      useSubmitting.value = false
    }
  })
}

// ==================== 按会员查询 ====================
function openMemberQuery() {
  memberId.value = undefined
  memberStatus.value = undefined
  memberList.value = []
  memberVisible.value = true
}

async function loadMemberHistory() {
  if (!memberId.value || memberId.value <= 0) {
    ElMessage.warning('请输入会员 ID')
    return
  }
  memberLoading.value = true
  try {
    const data = await listCouponHistoryByMember(memberId.value, memberStatus.value)
    memberList.value = data
  } catch (error) {
    console.error('按会员查询失败:', error)
  } finally {
    memberLoading.value = false
  }
}

// ==================== 初始化 ====================
onMounted(() => {
  loadData()
  loadCategoryOptions()
})
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
.form-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
  margin-top: 2px;
}
</style>
