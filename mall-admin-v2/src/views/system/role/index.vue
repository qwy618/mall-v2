<template>
  <div class="role">
    <div class="role__bar">
      <el-button type="primary" plain @click="openCreate">新增角色</el-button>
    </div>

    <el-table v-loading="loading" :data="list" border stripe class="role__table">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column prop="code" label="标识" min-width="120">
        <template #default="{ row }"><code class="role__code">{{ row.code }}</code></template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">{{
            row.status === 1 ? '启用' : '禁用'
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="可见菜单" min-width="120">
        <template #default="{ row }">
          <span class="role__muted">{{ (row.menuIds || []).length }} 个</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="openMenus(row)">分配菜单</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="formVisible" :title="form.id ? '编辑角色' : '新增角色'" width="440px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如 商品管理员" />
        </el-form-item>
        <el-form-item label="标识" prop="code">
          <el-input v-model="form.code" :disabled="!!form.id" placeholder="如 product（hasRole 用）" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="描述（可选）" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">启用</el-radio>
            <el-radio :value="0">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 分配菜单弹窗 -->
    <el-dialog v-model="menuVisible" title="分配可见菜单" width="560px">
      <div class="role__tip">
        勾选该角色可访问的菜单（对应前端路由）。保存后，拥有此角色的管理员登录时菜单随之变化。
      </div>
      <el-checkbox-group v-model="checkedMenuNames">
        <el-checkbox
          v-for="m in menuOptions"
          :key="m.name"
          :value="m.name"
          :label="m.title"
          border
          class="role__menu-item"
        />
      </el-checkbox-group>
      <template #footer>
        <el-button @click="menuVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitMenus">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { routes } from '@/router'
import {
  listRolesAPI,
  createRoleAPI,
  updateRoleAPI,
  deleteRoleAPI,
  updateRoleMenusAPI,
} from '@/apis/admin'
import type { UmsRole, UmsRoleDTO, MenuOption } from '@/types/admin'

const loading = ref(false)
const submitting = ref(false)
const list = ref<UmsRole[]>([])

// 菜单可选项直接由前端路由表生成（菜单真相源在前端）
const menuOptions = computed<MenuOption[]>(() => {
  const root = routes.find((r) => r.path === '/')
  return (root?.children ?? []).map((c) => ({
    name: String(c.name),
    title: String(c.meta?.title ?? c.name),
  }))
})

const formVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<UmsRoleDTO>({
  id: undefined,
  name: '',
  code: '',
  description: '',
  status: 1,
  sort: 0,
})
const rules: FormRules<UmsRoleDTO> = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入标识', trigger: 'blur' }],
}

const menuVisible = ref(false)
const menuTargetId = ref<number | null>(null)
const checkedMenuNames = ref<string[]>([])

async function fetchList() {
  loading.value = true
  try {
    list.value = await listRolesAPI()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.id = undefined
  form.name = ''
  form.code = ''
  form.description = ''
  form.status = 1
  form.sort = 0
  formVisible.value = true
  formRef.value?.clearValidate()
}
function openEdit(row: UmsRole) {
  form.id = row.id
  form.name = row.name
  form.code = row.code
  form.description = row.description || ''
  form.status = row.status ?? 1
  form.sort = row.sort ?? 0
  formVisible.value = true
  formRef.value?.clearValidate()
}

async function submitForm() {
  if (!formRef.value) return
  await formRef.value.validate(async (ok) => {
    if (!ok) return
    submitting.value = true
    try {
      if (form.id) await updateRoleAPI(form)
      else await createRoleAPI(form)
      ElMessage.success('已保存')
      formVisible.value = false
      fetchList()
    } finally {
      submitting.value = false
    }
  })
}

function openMenus(row: UmsRole) {
  menuTargetId.value = row.id
  checkedMenuNames.value = row.menuIds ? [...row.menuIds] : []
  menuVisible.value = true
}
async function submitMenus() {
  if (menuTargetId.value == null) return
  submitting.value = true
  try {
    await updateRoleMenusAPI({
      roleId: menuTargetId.value,
      menuIds: checkedMenuNames.value,
    })
    ElMessage.success('菜单已分配')
    menuVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

async function remove(row: UmsRole) {
  await ElMessageBox.confirm(`确认删除角色「${row.name}」？`, '提示', { type: 'warning' })
  await deleteRoleAPI(row.id)
  ElMessage.success('已删除')
  fetchList()
}

onMounted(fetchList)
</script>

<style scoped>
.role__bar {
  margin-bottom: 14px;
}
.role__table {
  width: 100%;
}
.role__code {
  background: var(--mall-primary-soft);
  color: var(--mall-primary);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 12px;
}
.role__muted {
  color: var(--admin-text-light);
}
.role__tip {
  font-size: 13px;
  color: var(--admin-text-light);
  margin-bottom: 12px;
}
.role__menu-item {
  margin-right: 8px;
  margin-bottom: 8px;
}
</style>
