<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-bar">
        <span>商品属性</span>
        <el-button type="primary" @click="openCreate">新增属性</el-button>
      </div>
    </template>

    <el-alert type="info" :closable="false" show-icon class="tip">
      <template #title>
        规格（SKU 级）决定价格与库存，其取值由「商品管理 → 编辑商品 → SKU」
        保存时自动同步，不需要在这里逐条维护；参数（商品级）只作展示，
        在「商品管理 → 编辑商品 → 规格参数」里填值。
      </template>
    </el-alert>

    <el-form :inline="true" class="filter-bar" @submit.prevent>
      <el-form-item label="分类">
        <el-select
            v-model="filterCategoryId"
            placeholder="全部分类"
            clearable
            filterable
            style="width: 200px"
        >
          <el-option v-for="o in categoryOptions" :key="o.id" :label="o.name" :value="o.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="filterType" placeholder="全部" clearable style="width: 140px">
          <el-option :value="0" label="规格" />
          <el-option :value="1" label="参数" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="list" v-loading="loading" border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="分类" width="140">
        <template #default="{ row }">{{ categoryName(row.categoryId) }}</template>
      </el-table-column>
      <el-table-column prop="name" label="属性名" width="150" />
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <el-tag :type="row.type === 0 ? 'warning' : 'success'">
            {{ row.type === 0 ? '规格' : '参数' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="录入方式" width="110">
        <template #default="{ row }">{{ row.inputType === 1 ? '列表选择' : '手工录入' }}</template>
      </el-table-column>
      <el-table-column prop="inputList" label="候选值" show-overflow-tooltip />
      <el-table-column prop="sort" label="排序" width="70" />
      <el-table-column label="操作" width="140">
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

    <el-dialog
        v-model="dialogVisible"
        :title="dialogMode === 'edit' ? '编辑属性' : '新增属性'"
        width="560px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="分类" prop="categoryId">
          <el-select v-model="form.categoryId" filterable placeholder="请选择分类" style="width: 100%">
            <el-option v-for="o in categoryOptions" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="属性名" prop="name">
          <el-input v-model="form.name" placeholder="如：颜色 / 容量 / 屏幕尺寸" />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-radio-group v-model="form.type">
            <el-radio :value="0">规格（影响价格库存）</el-radio>
            <el-radio :value="1">参数（仅展示）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="录入方式" prop="inputType">
          <el-radio-group v-model="form.inputType">
            <el-radio :value="1">从列表选择</el-radio>
            <el-radio :value="0">手工录入</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.inputType === 1" label="候选值">
          <el-input
              v-model="form.inputList"
              type="textarea"
              :rows="3"
              placeholder="逗号分隔，如：黑色,白色,蓝色"
          />
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" :precision="0" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import {
  createAttribute,
  deleteAttribute,
  listAttribute,
  updateAttribute,
} from '@/apis/attribute'
import { listCategory } from '@/apis/category'
import type { AttributeParam, ProductAttribute } from '@/types/attribute'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

// ==================== 列表状态 ====================
const list = ref<ProductAttribute[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)

// ==================== 筛选条件 ====================
const filterCategoryId = ref<number | undefined>(undefined)
const filterType = ref<number | undefined>(undefined)

// ==================== 分类下拉 ====================
const categoryOptions = ref<{ id: number; name: string }[]>([])
function categoryName(id: number): string {
  return categoryOptions.value.find((o) => o.id === id)?.name ?? String(id)
}

async function loadCategoryOptions() {
  try {
    // 传 parentId 为空 → 一次拿全部分类（属性挂的是叶子分类，如 T恤 / 手机通讯）
    const data = await listCategory(1, 500)
    categoryOptions.value = data.list.map((c) => ({ id: c.id, name: c.name }))
  } catch (error) {
    console.error('加载分类下拉失败:', error)
  }
}

// ==================== 弹窗 ====================
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<AttributeParam>({
  categoryId: 0,
  name: '',
  type: 0,
  inputType: 1,
  inputList: '',
  sort: 0,
})
const rules: FormRules<AttributeParam> = {
  categoryId: [{ required: true, type: 'number', min: 1, message: '请选择分类', trigger: 'change' }],
  name: [{ required: true, message: '请输入属性名', trigger: 'blur' }],
  type: [{ required: true, type: 'number', message: '请选择属性类型', trigger: 'change' }],
}

// ==================== 加载数据 ====================
async function loadData() {
  loading.value = true
  try {
    const data = await listAttribute({
      categoryId: filterCategoryId.value,
      type: filterType.value,
      pageNum: pageNum.value,
      pageSize: pageSize.value,
    })
    list.value = data.list
    total.value = data.total
  } catch (error) {
    console.error('加载属性列表失败:', error)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pageNum.value = 1
  loadData()
}

function handleReset() {
  filterCategoryId.value = undefined
  filterType.value = undefined
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

// ==================== 新增 / 编辑 ====================
function openCreate() {
  dialogMode.value = 'create'
  editId.value = null
  formRef.value?.resetFields()
  form.categoryId = filterCategoryId.value ?? 0
  form.name = ''
  form.type = 0
  form.inputType = 1
  form.inputList = ''
  form.sort = 0
  dialogVisible.value = true
}

function openEdit(row: ProductAttribute) {
  dialogMode.value = 'edit'
  editId.value = row.id
  form.categoryId = row.categoryId
  form.name = row.name
  form.type = row.type
  form.inputType = row.inputType
  form.inputList = row.inputList || ''
  form.sort = row.sort
  dialogVisible.value = true
}

async function submitForm() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      // 手工录入时不必保留候选值，清掉避免数据自相矛盾
      const payload: AttributeParam = {
        ...form,
        inputList: form.inputType === 1 ? form.inputList || '' : '',
      }
      if (dialogMode.value === 'create') {
        const id = await createAttribute(payload)
        ElMessage.success(`新增成功，ID=${id}`)
      } else {
        const affected = await updateAttribute(editId.value!, payload)
        ElMessage.success(`修改成功，影响 ${affected} 行`)
      }
      dialogVisible.value = false
      loadData()
    } catch (error) {
      // 后端 BusinessException 已经把可读原因放在 message 里（如"已被商品取值使用"），
      // 由 request 拦截器统一弹出，这里不再重复提示
      console.error('提交属性失败:', error)
    } finally {
      submitting.value = false
    }
  })
}

async function handleDelete(row: ProductAttribute) {
  try {
    await ElMessageBox.confirm(
      `确定删除属性「${row.name}」吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    const affected = await deleteAttribute(row.id)
    ElMessage.success(`删除成功，影响 ${affected} 行`)
    loadData()
  } catch (error) {
    console.error('删除属性失败:', error)
  }
}

// ==================== 初始化 ====================
onMounted(() => {
  loadCategoryOptions()
  loadData()
})
</script>

<style scoped>
.header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.tip {
  margin-bottom: 16px;
}
.filter-bar {
  margin-bottom: 16px;
}
</style>
