<template>
  <div class="usr">
    <!-- 工具栏 -->
    <div class="usr__bar">
      <el-input
        v-model="query.keyword"
        placeholder="用户名/昵称搜索"
        clearable
        style="width: 220px"
        @keyup.enter="onSearch"
        @clear="onSearch"
      />
      <el-button type="primary" @click="onSearch">查询</el-button>
      <el-button @click="onReset">重置</el-button>
      <el-button type="primary" plain @click="openCreate">新增管理员</el-button>
    </div>

    <!-- 表格 -->
    <el-table v-loading="loading" :data="list" border stripe class="usr__table">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="nickName" label="昵称" min-width="120" />
      <el-table-column prop="email" label="邮箱" min-width="160" />
      <el-table-column label="角色" min-width="140">
        <template #default="{ row }">
          <el-tag v-for="code in row.roles || []" :key="code" size="small" class="usr__role">{{
            roleName(code)
          }}</el-tag>
          <span v-if="!row.roles || !row.roles.length" class="usr__muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">{{
            row.status === 1 ? '启用' : '禁用'
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="openAssign(row)">分配角色</el-button>
          <el-button link :type="row.status === 1 ? 'warning' : 'success'" @click="toggleStatus(row)">{{
            row.status === 1 ? '禁用' : '启用'
          }}</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="usr__pager">
      <el-pagination
        layout="prev, pager, next, total"
        :total="total"
        :current-page="query.pageNum"
        :page-size="query.pageSize"
        @current-change="onPageChange"
      />
    </div>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="formVisible" :title="form.id ? '编辑管理员' : '新增管理员'" width="460px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="!!form.id" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item :label="form.id ? '密码' : '密码'" :prop="form.id ? '' : 'password'">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="form.id ? '留空则不修改' : '登录密码'"
          />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickName" placeholder="昵称" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="邮箱（可选）" />
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

    <!-- 分配角色弹窗 -->
    <el-dialog v-model="assignVisible" title="分配角色" width="420px">
      <el-checkbox-group v-model="checkedRoleIds">
        <el-checkbox v-for="r in roles" :key="r.id" :value="r.id" :label="r.name" border />
      </el-checkbox-group>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAssign">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  listAdminsAPI,
  createAdminAPI,
  updateAdminAPI,
  deleteAdminAPI,
  updateAdminStatusAPI,
  updateAdminRoleAPI,
  getAdminRolesAPI,
  listRolesAPI,
} from '@/apis/admin'
import type { UmsAdmin, UmsAdminDTO, UmsRole } from '@/types/admin'

const loading = ref(false)
const submitting = ref(false)
const list = ref<UmsAdmin[]>([])
const total = ref(0)
const query = reactive({ keyword: '', pageNum: 1, pageSize: 10 })
const roles = ref<UmsRole[]>([])

const formVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<UmsAdminDTO>({
  id: undefined,
  username: '',
  password: '',
  nickName: '',
  email: '',
  status: 1,
})
const rules: FormRules<UmsAdminDTO> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const assignVisible = ref(false)
const assignTargetId = ref<number | null>(null)
const checkedRoleIds = ref<number[]>([])

function roleName(code?: string) {
  return roles.value.find((r) => r.code === code)?.name || code || ''
}

async function fetchList() {
  loading.value = true
  try {
    const data = await listAdminsAPI({
      keyword: query.keyword || undefined,
      pageNum: query.pageNum,
      pageSize: query.pageSize,
    })
    list.value = data.list
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function fetchRoles() {
  roles.value = await listRolesAPI()
}

function onSearch() {
  query.pageNum = 1
  fetchList()
}
function onReset() {
  query.keyword = ''
  onSearch()
}
function onPageChange(p: number) {
  query.pageNum = p
  fetchList()
}

function openCreate() {
  form.id = undefined
  form.username = ''
  form.password = ''
  form.nickName = ''
  form.email = ''
  form.status = 1
  formVisible.value = true
  formRef.value?.clearValidate()
}
function openEdit(row: UmsAdmin) {
  form.id = row.id
  form.username = row.username
  form.password = ''
  form.nickName = row.nickName || ''
  form.email = row.email || ''
  form.status = row.status ?? 1
  formVisible.value = true
  formRef.value?.clearValidate()
}

async function submitForm() {
  if (!formRef.value) return
  await formRef.value.validate(async (ok) => {
    if (!ok) return
    submitting.value = true
    try {
      const payload: UmsAdminDTO = { ...form }
      if (form.id && !payload.password) delete payload.password
      if (form.id) await updateAdminAPI(payload)
      else await createAdminAPI(payload)
      ElMessage.success('已保存')
      formVisible.value = false
      fetchList()
    } finally {
      submitting.value = false
    }
  })
}

async function openAssign(row: UmsAdmin) {
  assignTargetId.value = row.id
  checkedRoleIds.value = await getAdminRolesAPI(row.id)
  assignVisible.value = true
}
async function submitAssign() {
  if (assignTargetId.value == null) return
  submitting.value = true
  try {
    await updateAdminRoleAPI({
      adminId: assignTargetId.value,
      roleIds: checkedRoleIds.value,
    })
    ElMessage.success('角色已更新')
    assignVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(row: UmsAdmin) {
  const next = row.status === 1 ? 0 : 1
  await updateAdminStatusAPI(row.id, next)
  ElMessage.success(next === 1 ? '已启用' : '已禁用')
  fetchList()
}

async function remove(row: UmsAdmin) {
  await ElMessageBox.confirm(`确认删除管理员「${row.username}」？`, '提示', {
    type: 'warning',
  })
  await deleteAdminAPI(row.id)
  ElMessage.success('已删除')
  fetchList()
}

onMounted(() => {
  fetchRoles()
  fetchList()
})
</script>

<style scoped>
.usr__bar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}
.usr__table {
  width: 100%;
}
.usr__pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
.usr__role {
  margin-right: 4px;
}
.usr__muted {
  color: var(--admin-text-light);
}
</style>
