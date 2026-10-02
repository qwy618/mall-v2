<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-bar">
        <span>品牌列表</span>
        <el-button type="primary" @click="openCreate">新增品牌</el-button>
      </div>
    </template>

    <!-- 表格 -->
    <el-table :data="list" v-loading="loading" border>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="品牌名称" />
      <el-table-column label="Logo" width="120">
        <template #default="{ row }">
          <el-image
              :src="row.logo"
              :preview-src-list="[row.logo]"
              fit="contain"
              style="width: 60px; height: 60px"
          />
        </template>
      </el-table-column>
      <el-table-column prop="sort" label="排序" width="80" />
      <el-table-column prop="createTime" label="创建时间" width="180" />
      <!-- 操作列：详情 / 编辑 / 删除 -->
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" link @click="openDetail(row.id)">详情</el-button>
          <el-button size="small" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页器 -->
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

    <!-- 详情弹窗：只读展示一个 Brand -->
    <el-dialog v-model="detailVisible" title="品牌详情" width="520px">
      <el-descriptions :column="1" border v-if="detailData">
        <el-descriptions-item label="ID">{{ detailData.id }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ detailData.name }}</el-descriptions-item>
        <el-descriptions-item label="描述">{{ detailData.description || '—' }}</el-descriptions-item>
        <el-descriptions-item label="Logo">
          <el-image :src="detailData.logo" fit="contain" style="width: 80px; height: 80px" />
        </el-descriptions-item>
        <el-descriptions-item label="排序">{{ detailData.sort }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detailData.createTime }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ detailData.updateTime }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 新增/编辑弹窗：el-form + 校验规则，提交按 mode 调 createBrand 或 updateBrand -->
    <el-dialog v-model="dialogVisible" :title="dialogMode === 'edit' ? '编辑品牌' : '新增品牌'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="2-64 个字符" />
        </el-form-item>
        <el-form-item label="Logo" prop="logo">
          <el-input v-model="form.logo" placeholder="图片 URL" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" />
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
import { ref, reactive, onMounted } from 'vue'
import {
  listBrand,
  createBrand,
  getBrandDetail,
  updateBrand,
  deleteBrand,
} from '@/apis/brand'
import type { Brand, BrandParam } from '@/types/brand'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

// ==================== 列表状态 ====================
const list = ref<Brand[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(5)
const loading = ref(false)

// ==================== 详情弹窗状态 ====================
const detailVisible = ref(false)
const detailData = ref<Brand | null>(null)

// ==================== 新增/编辑共用弹窗状态 ====================
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()
// form 字段严格对齐 BrandParam（不含 id / createTime / updateTime）
const form = reactive<BrandParam>({
  name: '',
  logo: '',
  description: '',
  sort: 0,
})
// 前端校验是“第一道防线”，后端 @Valid 才是最终防线
const rules: FormRules<BrandParam> = {
  name: [{ required: true, message: '请输入品牌名称', trigger: 'blur' }],
  logo: [{ required: true, message: '请输入 Logo 地址', trigger: 'blur' }],
}

// ==================== 加载数据 ====================
async function loadData() {
  loading.value = true
  try {
    const data = await listBrand(pageNum.value, pageSize.value)
    list.value = data.list
    total.value = data.total
  } catch (error) {
    console.error('加载品牌列表失败:', error)
  } finally {
    loading.value = false
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

// ★ 详情 —— 调 getBrandDetail 把返回值回填到详情弹窗
async function openDetail(id: number) {
  const data = await getBrandDetail(id)
  detailData.value = data
  detailVisible.value = true
}

// ★ 打开新增 —— 先清空表单再弹窗
function openCreate() {
  dialogMode.value = 'create'
  formRef.value?.resetFields()
  form.sort = 0
  dialogVisible.value = true
}

// ★ 打开编辑 —— 先用 id 拉详情，再只把 Param 白名单字段回填进表单（不拷 id/createTime/updateTime）
async function openEdit(row: Brand) {
  dialogMode.value = 'edit'
  editId.value = row.id
  try {
    const data = await getBrandDetail(row.id)
    form.name = data.name
    form.logo = data.logo
    form.description = data.description
    form.sort = data.sort
    dialogVisible.value = true
  } catch (error) {
    console.error('加载品牌详情失败:', error)
  }
}

// ★ 提交 —— 按 mode 走新增或编辑；成功后刷新列表（不手动插行，避免分页/总数不一致）
async function submitForm() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (dialogMode.value === 'create') {
        const id = await createBrand({ ...form })
        ElMessage.success(`新增成功，ID=${id}`)
      } else {
        const affected = await updateBrand(editId.value!, { ...form })
        ElMessage.success(`修改成功，影响 ${affected} 行`)
      }
      dialogVisible.value = false
      loadData()
    } catch (error) {
      console.error('提交品牌失败:', error)
    } finally {
      submitting.value = false
    }
  })
}

// ★ 删除 —— ElMessageBox 二次确认；用户取消则直接 return，不调接口
async function handleDelete(row: Brand) {
  try {
    await ElMessageBox.confirm(
      `确定删除品牌「${row.name}」吗？此操作不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    const affected = await deleteBrand(row.id)
    ElMessage.success(`删除成功，影响 ${affected} 行`)
    loadData()
  } catch (error) {
    console.error('删除品牌失败:', error)
  }
}

// ==================== 初始化 ====================
onMounted(() => {
  loadData()
})
</script>

<style scoped>
.header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
