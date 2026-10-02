<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-bar">
        <span>商品分类</span>
        <el-button type="primary" @click="openCreate">新增分类</el-button>
      </div>
    </template>

    <!-- 筛选区：按 parentId 过滤。
         选项来自真实的一级分类，而不是硬编码的 0/1/2 —— 原来的「二级分类=1」
         实际含义是「父级是 id=1 的分类」，标签与语义不符，会让人找不到数据。 -->
    <div class="filter-bar">
      <span>父级分类：</span>
      <el-select
        v-model="parentIdFilter"
        clearable
        placeholder="全部分类"
        style="width: 240px"
        @change="handleSearch"
      >
        <el-option label="顶级分类（无父级）" :value="0" />
        <el-option
          v-for="c in parentOptions"
          :key="c.id"
          :label="`${c.name} 的下级`"
          :value="c.id"
        />
      </el-select>
      <el-button @click="resetFilter">重置</el-button>
      <span class="filter-tip">共 {{ total }} 条</span>
    </div>

    <!-- 表格 -->
    <el-table :data="list" v-loading="loading" border>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="分类名称" />
      <el-table-column prop="parentId" label="父级ID" width="90" />
      <el-table-column prop="level" label="级别" width="70" />
      <el-table-column prop="sort" label="排序" width="70" />
      <el-table-column label="图标" width="80">
        <template #default="{ row }">
          <el-image v-if="isImgUrl(row.icon)" :src="row.icon" fit="contain" style="width: 40px; height: 40px" />
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="显示" width="80">
        <template #default="{ row }">
          <el-tag :type="row.showStatus === 1 ? 'success' : 'info'">
            {{ row.showStatus === 1 ? '显示' : '隐藏' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createTime" label="创建时间" width="180" />
      <el-table-column label="操作" width="180">
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

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="分类详情" width="520px">
      <el-descriptions :column="1" border v-if="detailData">
        <el-descriptions-item label="ID">{{ detailData.id }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ detailData.name }}</el-descriptions-item>
        <el-descriptions-item label="父级ID">{{ detailData.parentId }}</el-descriptions-item>
        <el-descriptions-item label="级别">{{ detailData.level }}</el-descriptions-item>
        <el-descriptions-item label="排序">{{ detailData.sort }}</el-descriptions-item>
        <el-descriptions-item label="图标">
          <el-image v-if="isImgUrl(detailData.icon)" :src="detailData.icon" fit="contain" style="width: 80px; height: 80px" />
          <span v-else>—</span>
        </el-descriptions-item>
        <el-descriptions-item label="显示状态">{{ detailData.showStatus === 1 ? '显示' : '隐藏' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detailData.createTime }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ detailData.updateTime }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 新增/编辑弹窗：共用 form，标题按 mode 动态 -->
    <el-dialog v-model="dialogVisible" :title="dialogMode === 'edit' ? '编辑分类' : '新增分类'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="84px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="必填" />
        </el-form-item>
        <el-form-item label="父级ID" prop="parentId">
          <el-input-number v-model="form.parentId" :min="0" />
        </el-form-item>
        <el-form-item label="级别" prop="level">
          <el-input-number v-model="form.level" :min="0" :max="2" />
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" />
        </el-form-item>
        <el-form-item label="图标" prop="icon">
          <el-input v-model="form.icon" placeholder="图片 URL（可选）" />
        </el-form-item>
        <el-form-item label="显示状态" prop="showStatus">
          <el-radio-group v-model="form.showStatus">
            <el-radio :value="1">显示</el-radio>
            <el-radio :value="0">隐藏</el-radio>
          </el-radio-group>
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
  listCategory,
  getCategoryDetail,
  createCategory,
  updateCategory,
  deleteCategory,
} from '@/apis/category'
import type { Category, CategoryParam } from '@/types/category'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

// ==================== 列表状态 ====================
const list = ref<Category[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(5)
const loading = ref(false)

// ==================== 筛选：parentId ====================
// null = 全部；0 = 顶级分类；其它值 = 以该分类 id 为父级的下级
const parentIdFilter = ref<number | null>(null)

// 父级候选：只可能是顶级分类（parentId=0），所以选项从数据里动态取
const parentOptions = ref<Category[]>([])

// ==================== 详情弹窗 ====================
const detailVisible = ref(false)
const detailData = ref<Category | null>(null)

// ==================== 新增/编辑共用弹窗 ====================
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<CategoryParam>({
  name: '',
  parentId: 0,
  level: 0,
  sort: 0,
  icon: '',
  showStatus: 1,
})
const rules: FormRules<CategoryParam> = {
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }],
  parentId: [{ required: true, message: '请输入父级ID', trigger: 'blur' }],
  level: [{ required: true, message: '请输入级别', trigger: 'blur' }],
  sort: [{ required: true, message: '请输入排序', trigger: 'blur' }],
  showStatus: [{ required: true, message: '请选择显示状态', trigger: 'change' }],
}

// 分类 icon 语义是图片 URL：只有像 URL 才当图片渲染（脏数据如字面量 "string" 忽略）
function isImgUrl(u?: string): boolean {
  return !!u && /^(https?:)?\/\//i.test(u)
}

// ==================== 加载数据 ====================
async function loadData() {
  loading.value = true
  try {
    // ★ 关键：parentIdFilter 为 null（全部）时传 undefined，axios 不会把 undefined 拼进 params
    //   → 请求变成 /category/list?pageNum=1&pageSize=5，后端 parentId 收到 null → 查全表
    //   选了一级分类时传 0 → 后端 eq(parent_id, 0) → 只查一级
    const data = await listCategory(
      pageNum.value,
      pageSize.value,
      parentIdFilter.value ?? undefined
    )
    list.value = data.list
    total.value = data.total
  } catch (error) {
    console.error('加载分类失败:', error)
  } finally {
    loading.value = false
  }
}

// ★ 父级下拉选项：拉一次全量分类，取 parentId=0 的作为可选父级
async function loadParentOptions() {
  try {
    const data = await listCategory(1, 100)
    parentOptions.value = data.list.filter((c) => c.parentId === 0)
  } catch (error) {
    console.error('加载父级分类选项失败:', error)
  }
}

// ==================== 筛选事件 ====================
function handleSearch() {
  pageNum.value = 1
  loadData()
}
function resetFilter() {
  parentIdFilter.value = null
  handleSearch()
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

// ★ 详情：调 getCategoryDetail 回填
async function openDetail(id: number) {
  const data = await getCategoryDetail(id)
  detailData.value = data
  detailVisible.value = true
}

// ★ 打开新增：清空表单
function openCreate() {
  dialogMode.value = 'create'
  formRef.value?.resetFields()
  form.parentId = 0
  form.level = 0
  form.sort = 0
  form.showStatus = 1
  dialogVisible.value = true
}

// ★ 打开编辑：拉详情后只回填 Param 白名单字段（parentId 可能为 null，用 ?? 0 兜底）
async function openEdit(row: Category) {
  dialogMode.value = 'edit'
  editId.value = row.id
  try {
    const data = await getCategoryDetail(row.id)
    form.name = data.name
    form.parentId = data.parentId ?? 0
    form.level = data.level
    form.sort = data.sort
    form.icon = data.icon
    form.showStatus = data.showStatus
    dialogVisible.value = true
  } catch (error) {
    console.error('加载分类详情失败:', error)
  }
}

// ★ 提交：按 mode 走新增或编辑，成功后刷新列表
async function submitForm() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (dialogMode.value === 'create') {
        const id = await createCategory({ ...form })
        ElMessage.success(`新增成功，ID=${id}`)
      } else {
        const affected = await updateCategory(editId.value!, { ...form })
        ElMessage.success(`修改成功，影响 ${affected} 行`)
      }
      dialogVisible.value = false
      loadData()
    } catch (error) {
      console.error('提交分类失败:', error)
    } finally {
      submitting.value = false
    }
  })
}

// ★ 删除：二次确认，用户取消则 return
async function handleDelete(row: Category) {
  try {
    await ElMessageBox.confirm(
      `确定删除分类「${row.name}」吗？此操作不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    const affected = await deleteCategory(row.id)
    ElMessage.success(`删除成功，影响 ${affected} 行`)
    loadData()
  } catch (error) {
    console.error('删除分类失败:', error)
  }
}

onMounted(() => {
  loadParentOptions()
  loadData()
})
</script>

<style scoped>
.header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.filter-tip {
  margin-left: 4px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
