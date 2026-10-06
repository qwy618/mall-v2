<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-bar">
        <span>订单管理</span>
        <div class="header-actions">
          <el-button @click="goReturn">售后管理</el-button>
          <el-button type="primary" @click="openCreate">模拟下单</el-button>
        </div>
      </div>
    </template>

    <!-- 筛选区 -->
    <el-form :inline="true" class="filter-bar" @submit.prevent>
      <el-form-item label="订单号">
        <el-input
            v-model="keyword"
            placeholder="订单号模糊"
            clearable
            style="width: 200px"
            @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filterStatus" placeholder="全部" clearable style="width: 130px">
          <el-option :value="0" label="待付款" />
          <el-option :value="1" label="已付款" />
          <el-option :value="2" label="已发货" />
          <el-option :value="3" label="已完成" />
          <el-option :value="4" label="已关闭" />
          <el-option :value="5" label="无效订单" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 主表格 -->
    <el-table :data="list" v-loading="loading" border :row-class-name="orderRowClass">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="ORDER_STATUS_TAG[row.status]">{{ ORDER_STATUS_TEXT[row.status] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="orderSn" label="订单号" width="190" />
      <el-table-column prop="memberId" label="会员ID" width="90" />
      <el-table-column prop="receiverName" label="收货人" width="110" />
      <el-table-column label="金额" width="120">
        <template #default="{ row }">¥{{ formatMoney(row.totalAmount) }}</template>
      </el-table-column>
      <el-table-column label="运费" width="90">
        <template #default="{ row }">¥{{ formatMoney(row.freightAmount) }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">{{ formatDateTime(row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="310" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button
              v-if="row.status === 0"
              size="small" link type="success" @click="handlePay(row)">支付</el-button>
          <el-button
              v-if="row.status === 0"
              size="small" link type="warning" @click="handleCancel(row)">取消</el-button>
          <el-button
              v-if="row.status === 1"
              size="small" link type="primary" @click="openShip(row)">发货</el-button>
          <el-button
              v-if="row.status === 1"
              size="small" link type="danger" @click="handleInvalidate(row)">作废</el-button>
          <el-button
              v-if="row.status === 2"
              size="small" link type="success" @click="handleComplete(row)">确认收货</el-button>
          <el-button
              size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
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

    <!-- 订单详情抽屉 -->
    <el-drawer v-model="detailVisible" title="订单详情" size="560px" @open="onDrawerOpen">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="订单号">{{ detail.order.orderSn }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="ORDER_STATUS_TAG[detail.order.status]">
              {{ ORDER_STATUS_TEXT[detail.order.status] }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="会员ID">{{ detail.order.memberId }}</el-descriptions-item>
          <el-descriptions-item label="收货人">{{ detail.order.receiverName }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ detail.order.receiverPhone }}</el-descriptions-item>
          <el-descriptions-item label="收货地址">
            {{ detail.order.receiverProvince }}{{ detail.order.receiverCity }}
            {{ detail.order.receiverDistrict }}{{ detail.order.receiverDetailAddress }}
          </el-descriptions-item>
          <el-descriptions-item label="商品金额">¥{{ formatMoney(detail.order.totalAmount) }}</el-descriptions-item>
          <el-descriptions-item label="运费">¥{{ formatMoney(detail.order.freightAmount) }}</el-descriptions-item>
          <el-descriptions-item label="物流" v-if="detail.order.deliveryCompany">
            {{ detail.order.deliveryCompany }} / {{ detail.order.deliverySn }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(detail.order.createTime) }}</el-descriptions-item>
          <el-descriptions-item label="支付时间" v-if="detail.order.paymentTime">{{ formatDateTime(detail.order.paymentTime) }}</el-descriptions-item>
          <el-descriptions-item label="发货时间" v-if="detail.order.deliveryTime">{{ formatDateTime(detail.order.deliveryTime) }}</el-descriptions-item>
          <el-descriptions-item label="完成时间" v-if="detail.order.receiveTime">{{ formatDateTime(detail.order.receiveTime) }}</el-descriptions-item>
        </el-descriptions>

        <el-divider>订单项</el-divider>
        <el-table :data="detail.items" border size="small">
          <el-table-column prop="productName" label="商品" show-overflow-tooltip />
          <el-table-column prop="skuCode" label="SKU编码" width="150" />
          <el-table-column prop="price" label="单价" width="90">
            <template #default="{ row }">¥{{ formatMoney(row.price) }}</template>
          </el-table-column>
          <el-table-column prop="quantity" label="数量" width="70" />
        </el-table>
      </template>
    </el-drawer>

    <!-- 发货弹窗 -->
    <el-dialog v-model="shipDialogVisible" title="发货" width="460px">
      <el-form ref="shipFormRef" :model="shipForm" :rules="shipRules" label-width="90px">
        <el-form-item label="物流公司" prop="deliveryCompany">
          <el-input v-model="shipForm.deliveryCompany" placeholder="如：顺丰" />
        </el-form-item>
        <el-form-item label="物流单号" prop="deliverySn">
          <el-input v-model="shipForm.deliverySn" placeholder="运单号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shipDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="shipSubmitting" @click="submitShip">确定发货</el-button>
      </template>
    </el-dialog>

    <!-- 模拟下单弹窗 -->
    <el-dialog v-model="createDialogVisible" title="模拟下单" width="620px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="90px">
        <el-form-item label="会员ID" prop="memberId">
          <el-input-number v-model="createForm.memberId" :min="1" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="地址ID" prop="addressId">
          <el-input-number v-model="createForm.addressId" :min="1" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="运费" prop="freightAmount">
          <el-input-number v-model="createForm.freightAmount" :min="0" :precision="2" :step="1" style="width: 100%" />
        </el-form-item>

        <el-divider>订单项</el-divider>
        <div class="item-bar">
          <span>商品行（SKU + 数量）</span>
          <el-button size="small" type="primary" @click="addItemRow">添加商品行</el-button>
        </div>
        <div v-for="(it, idx) in createForm.items" :key="idx" class="item-row">
          <el-input-number v-model="it.skuId" :min="1" :step="1" placeholder="SKU ID" style="width: 160px" />
          <el-input-number v-model="it.quantity" :min="1" :step="1" placeholder="数量" style="width: 140px" />
          <el-button size="small" link type="danger" @click="removeItemRow(idx)">移除</el-button>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="submitCreate">提交下单</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  listOrders,
  getOrderDetail,
  createOrder,
  payOrder,
  shipOrder,
  completeOrder,
  cancelOrder,
  deleteOrder,
  invalidateOrder,
} from '@/apis/order'
import { onAdminWsMessage } from '@/utils/adminWs'
import { formatDateTime } from '@/utils/format'
import {
  ORDER_STATUS_TEXT,
  ORDER_STATUS_TAG,
  type Order,
  type OrderDetailVO,
  type OrderParam,
  type OrderItemParam,
  type OrderShipParam,
  type OrderListParams,
} from '@/types/order'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

// ==================== 列表状态 ====================
const router = useRouter()
const list = ref<Order[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)

// 新订单实时置顶高亮
const flashId = ref<number | string>('')
function orderRowClass({ row }: { row: Order }) {
  return row.id === flashId.value ? 'order-flash' : ''
}

// ==================== 筛选条件 ====================
const keyword = ref('')
const filterStatus = ref<number | undefined>(undefined)

// ==================== 加载数据 ====================
function goReturn() {
  router.push('/return')
}

async function loadData() {
  loading.value = true
  try {
    const params: OrderListParams = {
      pageNum: pageNum.value,
      pageSize: pageSize.value,
    }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (filterStatus.value !== undefined && filterStatus.value !== null) params.status = filterStatus.value
    const data = await listOrders(params)
    list.value = data.list
    total.value = data.total
  } catch (error) {
    console.error('加载订单列表失败:', error)
  } finally {
    loading.value = false
  }
}

function formatMoney(v?: number): string {
  return (v ?? 0).toFixed(2)
}

function handleSearch() {
  pageNum.value = 1
  loadData()
}

function handleReset() {
  keyword.value = ''
  filterStatus.value = undefined
  pageNum.value = 1
  loadData()
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

// ==================== 订单详情抽屉 ====================
const detailVisible = ref(false)
const detail = ref<OrderDetailVO | null>(null)
let currentId = 0

function openDetail(row: Order) {
  currentId = row.id
  detailVisible.value = true
}
async function onDrawerOpen() {
  try {
    detail.value = await getOrderDetail(currentId)
  } catch (error) {
    console.error('加载订单详情失败:', error)
  }
}

// ==================== 状态操作 ====================
async function handlePay(row: Order) {
  try {
    await payOrder(row.id)
    ElMessage.success('支付成功')
    loadData()
  } catch (error) {
    console.error('支付失败:', error)
  }
}

async function handleComplete(row: Order) {
  try {
    await completeOrder(row.id)
    ElMessage.success('已确认收货')
    loadData()
  } catch (error) {
    console.error('确认收货失败:', error)
  }
}

async function handleCancel(row: Order) {
  try {
    await ElMessageBox.confirm(
      `确定取消订单「${row.orderSn}」吗？库存将自动还原。`,
      '取消确认',
      { type: 'warning', confirmButtonText: '取消订单', cancelButtonText: '返回' }
    )
  } catch {
    return
  }
  try {
    await cancelOrder(row.id)
    ElMessage.success('订单已取消，库存已还原')
    loadData()
  } catch (error) {
    console.error('取消订单失败:', error)
  }
}

async function handleInvalidate(row: Order) {
  let note = ''
  try {
    const res = await ElMessageBox.prompt(
      `确定作废订单「${row.orderSn}」吗？将退款 ¥${formatMoney(row.payAmount)}，并回滚库存、退回优惠券与抵扣积分。`,
      '作废确认',
      {
        type: 'warning',
        confirmButtonText: '确认作废',
        cancelButtonText: '返回',
        inputPlaceholder: '作废原因（可选）',
        inputValue: '',
      }
    )
    note = res.value || ''
  } catch {
    return
  }
  try {
    await invalidateOrder(row.id, note || undefined)
    ElMessage.success('订单已作废：已退款并回滚库存 / 优惠券 / 抵扣积分')
    loadData()
  } catch (error) {
    console.error('作废订单失败:', error)
  }
}

async function handleDelete(row: Order) {
  try {
    await ElMessageBox.confirm(
      `确定删除订单「${row.orderSn}」吗？此操作不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    const affected = await deleteOrder(row.id)
    ElMessage.success(`删除成功，影响 ${affected} 行`)
    loadData()
  } catch (error) {
    console.error('删除订单失败:', error)
  }
}

// ==================== 发货弹窗 ====================
const shipDialogVisible = ref(false)
const shipSubmitting = ref(false)
const shipFormRef = ref<FormInstance>()
const shipForm = reactive<OrderShipParam>({ deliveryCompany: '', deliverySn: '' })
const shipRules: FormRules<OrderShipParam> = {
  deliveryCompany: [{ required: true, message: '请输入物流公司', trigger: 'blur' }],
  deliverySn: [{ required: true, message: '请输入物流单号', trigger: 'blur' }],
}
let shipId = 0

function openShip(row: Order) {
  shipId = row.id
  shipFormRef.value?.resetFields()
  shipForm.deliveryCompany = ''
  shipForm.deliverySn = ''
  shipDialogVisible.value = true
}
async function submitShip() {
  if (!shipFormRef.value) return
  await shipFormRef.value.validate(async (valid) => {
    if (!valid) return
    shipSubmitting.value = true
    try {
      await shipOrder(shipId, { ...shipForm })
      ElMessage.success('发货成功')
      shipDialogVisible.value = false
      loadData()
    } catch (error) {
      console.error('发货失败:', error)
    } finally {
      shipSubmitting.value = false
    }
  })
}

// ==================== 模拟下单弹窗 ====================
const createDialogVisible = ref(false)
const createSubmitting = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive<OrderParam>({
  memberId: 1,
  addressId: 1,
  freightAmount: 0,
  items: [{ skuId: 1, quantity: 1 }],
})
const createRules: FormRules<OrderParam> = {
  memberId: [{ required: true, type: 'number', min: 1, message: '会员ID必填', trigger: 'blur' }],
  addressId: [{ required: true, type: 'number', min: 1, message: '地址ID必填', trigger: 'blur' }],
}

function openCreate() {
  createFormRef.value?.resetFields()
  createForm.memberId = 1
  createForm.addressId = 1
  createForm.freightAmount = 0
  createForm.items = [{ skuId: 1, quantity: 1 }]
  createDialogVisible.value = true
}
function addItemRow() {
  createForm.items.push({ skuId: 1, quantity: 1 })
}
function removeItemRow(idx: number) {
  if (createForm.items.length <= 1) return
  createForm.items.splice(idx, 1)
}
async function submitCreate() {
  if (!createFormRef.value) return
  await createFormRef.value.validate(async (valid) => {
    if (!valid) return
    // 每个 item 还要校验 skuId/quantity 合法
    if (createForm.items.some((it) => !it.skuId || it.skuId <= 0 || !it.quantity || it.quantity <= 0)) {
      ElMessage.warning('请填写有效的 SKU ID 与数量')
      return
    }
    createSubmitting.value = true
    try {
      const items: OrderItemParam[] = createForm.items.map((it) => ({ skuId: it.skuId, quantity: it.quantity }))
      const id = await createOrder({
        memberId: createForm.memberId,
        addressId: createForm.addressId,
        freightAmount: createForm.freightAmount,
        items,
      })
      ElMessage.success(`下单成功，订单ID=${id}`)
      createDialogVisible.value = false
      loadData()
    } catch (error) {
      console.error('下单失败:', error)
    } finally {
      createSubmitting.value = false
    }
  })
}

// ==================== 实时新订单（WebSocket 置顶） ====================
const unsubWs = onAdminWsMessage((msg) => {
  if (!msg || msg.type !== 'NEW_ORDER' || !msg.payload) return
  // 仅在第一页且无筛选时把新订单置顶，避免打乱筛选/分页结果
  if (pageNum.value === 1 && filterStatus.value === undefined && !keyword.value.trim()) {
    const p = msg.payload
    const row = {
      id: p.orderId,
      orderSn: p.orderSn,
      memberId: p.memberId,
      totalAmount: p.totalAmount,
      status: 1,
      createTime: p.createTime,
    } as unknown as Order
    list.value.unshift(row)
    total.value += 1
    flashId.value = row.id
    window.setTimeout(() => {
      if (flashId.value === row.id) flashId.value = ''
    }, 4000)
  }
})

// ==================== 初始化 ====================
onMounted(() => {
  loadData()
})
onUnmounted(() => unsubWs())
</script>

<style scoped>
.header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-actions {
  display: flex;
  gap: 10px;
}
.filter-bar {
  margin-bottom: 16px;
}
.item-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.item-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
:deep(.order-flash) td {
  animation: orderFlash 1.2s ease-in-out 2;
}
@keyframes orderFlash {
  0%, 100% { background-color: transparent; }
  50% { background-color: #f7ece0; }
}
</style>
