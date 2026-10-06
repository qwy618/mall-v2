<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-bar">
        <span>商品列表</span>
        <el-button type="primary" @click="openCreate">新增商品</el-button>
      </div>
    </template>

    <!-- 筛选区 -->
    <el-form :inline="true" class="filter-bar" @submit.prevent>
      <el-form-item label="关键词">
        <el-input
            v-model="keyword"
            placeholder="商品名称/货号"
            clearable
            style="width: 180px"
            @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="品牌">
        <el-select v-model="filterBrandId" placeholder="全部" clearable style="width: 150px">
          <el-option v-for="o in brandOptions" :key="o.id" :label="o.name" :value="o.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="filterCategoryId" placeholder="全部" clearable style="width: 150px">
          <el-option v-for="o in categoryOptions" :key="o.id" :label="o.name" :value="o.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filterStatus" placeholder="全部" clearable style="width: 110px">
          <el-option :value="1" label="上架" />
          <el-option :value="0" label="下架" />
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
      <el-table-column prop="productSn" label="货号" width="170" />
      <el-table-column prop="name" label="商品名称" />
      <el-table-column prop="subTitle" label="副标题" show-overflow-tooltip />
      <el-table-column label="品牌" width="120">
        <template #default="{ row }">{{ brandName(row.brandId) }}</template>
      </el-table-column>
      <el-table-column label="分类" width="120">
        <template #default="{ row }">{{ categoryName(row.categoryId) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'">
            {{ row.status === 1 ? '上架' : '下架' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="sale" label="销量" width="80" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
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

    <!-- 商品新增/编辑弹窗 -->
    <el-dialog
        v-model="dialogVisible"
        :title="dialogMode === 'edit' ? '编辑商品' : '新增商品'"
        width="780px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入商品名称" />
        </el-form-item>
        <el-form-item label="副标题" prop="subTitle">
          <el-input v-model="form.subTitle" placeholder="可选" />
        </el-form-item>
        <el-form-item label="主图" prop="pic">
          <div class="upload-row">
            <el-upload
              :show-file-list="false"
              accept="image/*"
              :before-upload="beforeUpload"
              :http-request="handleProductUpload"
            >
              <el-button type="primary">点击上传</el-button>
            </el-upload>
            <el-input v-model="form.pic" placeholder="或粘贴图片 URL，可选" style="flex: 1" />
          </div>
          <el-image
            v-if="form.pic"
            :src="form.pic"
            fit="cover"
            style="width: 80px; height: 80px; border-radius: 6px; margin-top: 8px"
          />
        </el-form-item>
        <el-form-item label="品牌" prop="brandId">
          <el-select v-model="form.brandId" placeholder="请选择品牌" style="width: 100%">
            <el-option v-for="o in brandOptions" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类" prop="categoryId">
          <el-select v-model="form.categoryId" placeholder="请选择分类" style="width: 100%">
            <el-option v-for="o in categoryOptions" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="form.status" style="width: 100%">
            <el-option :value="1" label="上架" />
            <el-option :value="0" label="下架" />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- SKU 区：仅编辑模式显示，内嵌当前商品的 SKU 子表格 -->
      <el-divider v-if="dialogMode === 'edit'">SKU 管理</el-divider>
      <div v-if="dialogMode === 'edit'">
        <div class="sku-bar">
          <span>该商品的 SKU（库存规格）</span>
          <el-button size="small" type="primary" @click="openSkuCreate">添加 SKU</el-button>
        </div>
        <el-table :data="skuList" v-loading="skuLoading" border size="small">
          <el-table-column prop="skuCode" label="SKU 编码" width="160" />
          <el-table-column label="规格" show-overflow-tooltip>
            <template #default="{ row }">{{ specText(row.spData) }}</template>
          </el-table-column>
          <el-table-column prop="price" label="价格" width="100" />
          <el-table-column prop="stock" label="库存" width="80" />
          <el-table-column prop="lockStock" label="锁定" width="80" />
          <el-table-column prop="sale" label="销量" width="80" />
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button size="small" link type="primary" @click="openSkuEdit(row)">编辑</el-button>
              <el-button size="small" link type="danger" @click="handleSkuDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 规格参数（type=1，商品级、仅展示）：填值后随商品的「确定」一起保存 -->
      <el-divider v-if="dialogMode === 'edit'">规格参数</el-divider>
      <div v-if="dialogMode === 'edit'">
        <el-form label-width="90px">
          <el-form-item v-for="a in paramAttrs" :key="a.id" :label="a.name">
            <el-input v-model="paramValues[a.id]" :placeholder="`请输入${a.name}`" />
          </el-form-item>
        </el-form>
        <el-alert
            v-if="!paramAttrs.length"
            type="info"
            :closable="false"
            show-icon
            title="该分类还没有参数属性。参数只作展示（如 屏幕尺寸 / 处理器），请先到「商品属性」添加。"
        />
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- SKU 新增/编辑子弹窗 -->
    <el-dialog
        v-model="skuDialogVisible"
        :title="skuDialogMode === 'edit' ? '编辑 SKU' : '添加 SKU'"
        width="520px"
    >
      <el-form ref="skuFormRef" :model="skuForm" :rules="skuRules" label-width="90px">
        <!-- 规格：按该商品所属分类的属性定义逐项选值，不再手敲 JSON（债务1）。
             提交时由 buildSpData() 拼回 sp_data —— sp_data 仍是真源，后端再从它同步派生索引。 -->
        <el-form-item label="规格">
          <div class="spec-rows">
            <div v-for="a in specAttrs" :key="a.id" class="spec-row">
              <span class="spec-row__name">{{ a.name }}</span>
              <el-select
                  v-if="a.inputType === 1"
                  v-model="specValues[a.id]"
                  filterable
                  allow-create
                  default-first-option
                  clearable
                  placeholder="选择，或输入新值"
                  style="flex: 1"
              >
                <el-option v-for="v in optionsOf(a)" :key="v" :label="v" :value="v" />
              </el-select>
              <el-input v-else v-model="specValues[a.id]" placeholder="请输入" style="flex: 1" />
            </div>
            <div v-if="!specAttrs.length" class="spec-empty">
              该分类还没有规格属性，请先到「商品属性」添加（如：颜色、容量）
            </div>
          </div>
        </el-form-item>
        <el-form-item label="价格" prop="price">
          <el-input-number v-model="skuForm.price" :min="0.01" :precision="2" :step="0.01" style="width: 100%" />
        </el-form-item>
        <el-form-item label="库存" prop="stock">
          <el-input-number v-model="skuForm.stock" :min="0" :precision="0" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="锁定库存" prop="lockStock">
          <el-input-number v-model="skuForm.lockStock" :min="0" :precision="0" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="销量" prop="sale">
          <el-input-number v-model="skuForm.sale" :min="0" :precision="0" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="主图" prop="pic">
          <div class="upload-row">
            <el-upload
              :show-file-list="false"
              accept="image/*"
              :before-upload="beforeUpload"
              :http-request="handleSkuUpload"
            >
              <el-button type="primary">点击上传</el-button>
            </el-upload>
            <el-input v-model="skuForm.pic" placeholder="或粘贴图片 URL，可空" style="flex: 1" />
          </div>
          <el-image
            v-if="skuForm.pic"
            :src="skuForm.pic"
            fit="cover"
            style="width: 80px; height: 80px; border-radius: 6px; margin-top: 8px"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="skuDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="skuSubmitting" @click="submitSku">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import {
  listProduct,
  getProductDetail,
  createProduct,
  updateProduct,
  deleteProduct,
} from '@/apis/product'
import {
  listSkuByProduct,
  createSku,
  updateSku,
  deleteSku,
} from '@/apis/sku'
import {
  getProductParams,
  listAttributeByProduct,
  saveProductParams,
} from '@/apis/attribute'
import type { AttributeItem, ProductAttribute } from '@/types/attribute'
import { listBrand } from '@/apis/brand'
import { listCategory } from '@/apis/category'
import type { Product, ProductParam } from '@/types/product'
import type { ProductListParams } from '@/apis/product'
import type { Sku, SkuParam } from '@/types/sku'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
  type UploadRequestOptions,
} from 'element-plus'
import { uploadOss } from '@/apis/oss'

// ==================== 列表状态 ====================
const list = ref<Product[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)

// ==================== 筛选条件 ====================
const keyword = ref('')
const filterBrandId = ref<number | undefined>(undefined)
const filterCategoryId = ref<number | undefined>(undefined)
const filterStatus = ref<number | undefined>(undefined)

// ==================== 品牌/分类下拉 ====================
const brandOptions = ref<{ id: number; name: string }[]>([])
const categoryOptions = ref<{ id: number; name: string }[]>([])
function brandName(id: number): string {
  return brandOptions.value.find((o) => o.id === id)?.name ?? String(id)
}
function categoryName(id: number): string {
  return categoryOptions.value.find((o) => o.id === id)?.name ?? String(id)
}

// ==================== 商品新增/编辑弹窗 ====================
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<ProductParam>({
  name: '',
  subTitle: '',
  pic: '',
  brandId: 0,
  categoryId: 0,
  status: 1,
})
const rules: FormRules<ProductParam> = {
  name: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
  brandId: [{ required: true, type: 'number', min: 1, message: '请选择品牌', trigger: 'change' }],
  categoryId: [{ required: true, type: 'number', min: 1, message: '请选择分类', trigger: 'change' }],
}

// ==================== SKU 子表格 ====================
const skuList = ref<Sku[]>([])
const skuLoading = ref(false)
const skuDialogVisible = ref(false)
const skuDialogMode = ref<'create' | 'edit'>('create')
const skuEditId = ref<number | null>(null)
const skuSubmitting = ref(false)
const skuFormRef = ref<FormInstance>()
const skuForm = reactive<SkuParam>({
  productId: 0,
  spData: '',
  price: 0,
  stock: 0,
  lockStock: 0,
  pic: '',
  sale: 0,
})
const skuRules: FormRules<SkuParam> = {
  price: [{ required: true, type: 'number', min: 0.01, message: '价格必须大于 0', trigger: 'blur' }],
}

// ==================== 属性（债务1） ====================
/** 当前商品所属分类下的「规格」属性定义（type=0）：SKU 表单按它逐项选值 */
const specAttrs = ref<ProductAttribute[]>([])
/** attributeId -> 该 SKU 在这个规格上的取值；提交时由 buildSpData() 拼回 sp_data */
const specValues = ref<Record<number, string>>({})
/** 当前商品所属分类下的「参数」属性定义（type=1）：商品级、仅展示 */
const paramAttrs = ref<ProductAttribute[]>([])
/** attributeId -> 该商品在这个参数上的值 */
const paramValues = ref<Record<number, string>>({})

// ==================== 加载数据 ====================
async function loadData() {
  loading.value = true
  try {
    const params: ProductListParams = {
      pageNum: pageNum.value,
      pageSize: pageSize.value,
    }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (filterBrandId.value) params.brandId = filterBrandId.value
    if (filterCategoryId.value) params.categoryId = filterCategoryId.value
    if (filterStatus.value !== undefined && filterStatus.value !== null) params.status = filterStatus.value
    const data = await listProduct(params)
    list.value = data.list
    total.value = data.total
  } catch (error) {
    console.error('加载商品列表失败:', error)
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
  filterBrandId.value = undefined
  filterCategoryId.value = undefined
  filterStatus.value = undefined
  pageNum.value = 1
  loadData()
}

async function loadBrandOptions() {
  try {
    const data = await listBrand(1, 100)
    brandOptions.value = data.list.map((b) => ({ id: b.id, name: b.name }))
  } catch (error) {
    console.error('加载品牌下拉失败:', error)
  }
}

async function loadCategoryOptions() {
  try {
    const data = await listCategory(1, 100)
    categoryOptions.value = data.list.map((c) => ({ id: c.id, name: c.name }))
  } catch (error) {
    console.error('加载分类下拉失败:', error)
  }
}

async function loadSkuList() {
  if (!editId.value) return
  skuLoading.value = true
  try {
    const data = await listSkuByProduct(editId.value, 1, 100)
    skuList.value = data.list
  } catch (error) {
    console.error('加载 SKU 列表失败:', error)
  } finally {
    skuLoading.value = false
  }
}

// ==================== 属性（债务1） ====================
/** 加载该商品所属分类下的属性定义：规格(type=0) 给 SKU 表单，参数(type=1) 给商品参数表单 */
async function loadAttributeDefs() {
  if (!editId.value) return
  try {
    const [specs, params] = await Promise.all([
      listAttributeByProduct(editId.value, 0),
      listAttributeByProduct(editId.value, 1),
    ])
    specAttrs.value = specs
    paramAttrs.value = params
  } catch (error) {
    console.error('加载属性定义失败:', error)
  }
}

/** 加载该商品已填的参数值，回填到 paramValues */
async function loadProductParams() {
  if (!editId.value) return
  try {
    const items = await getProductParams(editId.value)
    const map: Record<number, string> = {}
    for (const it of items) map[it.attributeId] = it.value
    paramValues.value = map
  } catch (error) {
    console.error('加载商品参数失败:', error)
  }
}

/** 参数表单 → 提交数组（空值不提交；后端本身也是先清后插） */
function collectParamItems(): AttributeItem[] {
  return paramAttrs.value
    .map((a) => ({ attributeId: a.id, value: (paramValues.value[a.id] || '').trim() }))
    .filter((it) => it.value !== '')
}

/** 候选值字符串（逗号分隔）→ 下拉选项 */
function optionsOf(attr: ProductAttribute): string[] {
  return (attr.inputList || '')
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s !== '')
}

/** specValues → sp_data JSON 文本；一项都没填返回空串（表示该 SKU 无规格） */
function buildSpData(): string {
  const items = specAttrs.value
    .map((a) => ({ key: a.name, value: (specValues.value[a.id] || '').trim() }))
    .filter((it) => it.value !== '')
  return items.length ? JSON.stringify(items) : ''
}

/** 把已有 sp_data 回填进 specValues。按「属性名」匹配定义（sp_data 里存的就是属性名） */
function fillSpecValues(spData?: string) {
  const map: Record<number, string> = {}
  if (spData) {
    try {
      const arr = JSON.parse(spData)
      if (Array.isArray(arr)) {
        for (const it of arr) {
          const key = it?.key ?? it?.name
          const value = it?.value ?? it?.val
          if (!key || !value) continue
          const attr = specAttrs.value.find((a) => a.name === key)
          if (attr) map[attr.id] = String(value)
        }
      }
    } catch {
      // 历史脏数据（非法 JSON）：当作没填，让运营重新选一遍，而不是把原文塞回输入框
    }
  }
  specValues.value = map
}

/**
 * 表格展示用：sp_data → 「颜色:黑色  容量:256G」。**仅供展示**。
 * 业务口径的规格格式化以 portal-web/src/utils/spec.ts 为准
 * （两个应用不共享代码，故这里只做最小实现）。
 */
function specText(spData?: string): string {
  if (!spData) return ''
  try {
    const arr = JSON.parse(spData)
    if (!Array.isArray(arr)) return spData
    return arr
      .map((it) =>
        it && typeof it === 'object'
          ? `${it.key ?? it.name ?? ''}:${it.value ?? it.val ?? ''}`
          : String(it)
      )
      .filter((s) => s !== ':')
      .join('  ')
  } catch {
    return spData
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

// ==================== 商品 / SKU 图片上传（MinIO） ====================
function beforeUpload(file: File) {
  const okTypes = ['image/jpeg', 'image/png', 'image/webp']
  if (!okTypes.includes(file.type)) {
    ElMessage.error('仅支持 JPG / PNG / WEBP 格式')
    return false
  }
  if (file.size / 1024 / 1024 > 2) {
    ElMessage.error('图片大小不能超过 2MB')
    return false
  }
  return true
}

async function handleProductUpload(option: UploadRequestOptions) {
  try {
    const url = await uploadOss(option.file)
    form.pic = url
    ElMessage.success('商品主图上传成功')
  } catch {
    ElMessage.error('上传失败')
  }
}

async function handleSkuUpload(option: UploadRequestOptions) {
  try {
    const url = await uploadOss(option.file)
    skuForm.pic = url
    ElMessage.success('SKU 主图上传成功')
  } catch {
    ElMessage.error('上传失败')
  }
}

// ==================== 商品 新增/编辑 ====================
function openCreate() {
  dialogMode.value = 'create'
  formRef.value?.resetFields()
  form.name = ''
  form.subTitle = ''
  form.pic = ''
  form.brandId = 0
  form.categoryId = 0
  form.status = 1
  dialogVisible.value = true
}

async function openEdit(row: Product) {
  dialogMode.value = 'edit'
  editId.value = row.id
  try {
    const data = await getProductDetail(row.id)
    form.name = data.name
    form.subTitle = data.subTitle || ''
    form.pic = data.pic || ''
    form.brandId = data.brandId
    form.categoryId = data.categoryId
    form.status = data.status
    // 属性定义必须先就位：SKU 表单按它渲染规格项，参数表单按它渲染输入框
    await loadAttributeDefs()
    dialogVisible.value = true
    await Promise.all([loadSkuList(), loadProductParams()])
  } catch (error) {
    console.error('加载商品详情失败:', error)
  }
}

async function submitForm() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (dialogMode.value === 'create') {
        const id = await createProduct({ ...form })
        ElMessage.success(`新增成功，ID=${id}`)
      } else {
        const affected = await updateProduct(editId.value!, { ...form })
        // 参数（type=1）随商品一起保存：后端先清后插，空值项不提交
        await saveProductParams(editId.value!, collectParamItems())
        ElMessage.success(`修改成功，影响 ${affected} 行`)
      }
      dialogVisible.value = false
      loadData()
    } catch (error) {
      console.error('提交商品失败:', error)
    } finally {
      submitting.value = false
    }
  })
}

async function handleDelete(row: Product) {
  try {
    await ElMessageBox.confirm(
      `确定删除商品「${row.name}」吗？此操作不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    const affected = await deleteProduct(row.id)
    ElMessage.success(`删除成功，影响 ${affected} 行`)
    loadData()
  } catch (error) {
    console.error('删除商品失败:', error)
  }
}

// ==================== SKU 新增/编辑 ====================
function openSkuCreate() {
  skuDialogMode.value = 'create'
  skuFormRef.value?.resetFields()
  skuForm.productId = editId.value! // 归属当前编辑的商品
  skuForm.spData = ''
  skuForm.price = 0
  skuForm.stock = 0
  skuForm.lockStock = 0
  skuForm.pic = ''
  skuForm.sale = 0
  specValues.value = {}            // 规格项清空
  skuDialogVisible.value = true
}

function openSkuEdit(sku: Sku) {
  skuDialogMode.value = 'edit'
  skuEditId.value = sku.id
  skuForm.productId = sku.productId
  skuForm.spData = sku.spData || ''
  skuForm.price = sku.price
  skuForm.stock = sku.stock
  skuForm.lockStock = sku.lockStock
  skuForm.pic = sku.pic || ''
  skuForm.sale = sku.sale
  fillSpecValues(sku.spData)       // 已有规格回填到下拉，而不是让运营重敲
  skuDialogVisible.value = true
}

async function submitSku() {
  if (!skuFormRef.value) return
  await skuFormRef.value.validate(async (valid) => {
    if (!valid) return
    skuSubmitting.value = true
    try {
      // 下拉选值 → sp_data（真源）；后端再据它同步 sku_attribute_value 派生索引
      skuForm.spData = buildSpData()
      if (skuDialogMode.value === 'create') {
        const id = await createSku({ ...skuForm })
        ElMessage.success(`SKU 新增成功，ID=${id}`)
      } else {
        const affected = await updateSku(skuEditId.value!, { ...skuForm })
        ElMessage.success(`SKU 修改成功，影响 ${affected} 行`)
      }
      skuDialogVisible.value = false
      await loadSkuList()
      // 运营可能在下拉里直接输入了新值，后端会把它追加进候选值清单 → 重拉定义保持一致
      await loadAttributeDefs()
    } catch (error) {
      console.error('提交 SKU 失败:', error)
    } finally {
      skuSubmitting.value = false
    }
  })
}

async function handleSkuDelete(sku: Sku) {
  try {
    await ElMessageBox.confirm(
      `确定删除 SKU「${sku.skuCode}」吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    const affected = await deleteSku(sku.id)
    ElMessage.success(`删除成功，影响 ${affected} 行`)
    await loadSkuList()
  } catch (error) {
    console.error('删除 SKU 失败:', error)
  }
}

// ==================== 初始化 ====================
onMounted(() => {
  loadData()
  loadBrandOptions()
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
.sku-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
/* SKU 表单的规格项：属性名 + 选值控件（替代原先手敲 JSON 的 textarea） */
.spec-rows {
  width: 100%;
}
.spec-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.spec-row + .spec-row {
  margin-top: 8px;
}
.spec-row__name {
  flex: 0 0 64px;
  color: var(--admin-text-light);
  font-size: 13px;
}
.spec-empty {
  color: var(--admin-text-light);
  font-size: 12px;
  line-height: 1.6;
}
.upload-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.upload-tip {
  color: var(--admin-text-light);
  font-size: 12px;
  margin-top: 4px;
}
</style>
