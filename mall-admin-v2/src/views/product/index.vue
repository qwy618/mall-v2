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
          <el-table-column prop="spData" label="规格" show-overflow-tooltip />
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
        <el-form-item label="规格" prop="spData">
          <el-input v-model="skuForm.spData" type="textarea" :rows="2" placeholder="规格 JSON，可空" />
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
    dialogVisible.value = true
    await loadSkuList()
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
  skuDialogVisible.value = true
}

async function submitSku() {
  if (!skuFormRef.value) return
  await skuFormRef.value.validate(async (valid) => {
    if (!valid) return
    skuSubmitting.value = true
    try {
      if (skuDialogMode.value === 'create') {
        const id = await createSku({ ...skuForm })
        ElMessage.success(`SKU 新增成功，ID=${id}`)
      } else {
        const affected = await updateSku(skuEditId.value!, { ...skuForm })
        ElMessage.success(`SKU 修改成功，影响 ${affected} 行`)
      }
      skuDialogVisible.value = false
      await loadSkuList()
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
