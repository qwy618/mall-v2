<template>
  <div class="addr">
    <div class="addr__head">
      <h3 class="addr__title">收货地址</h3>
      <el-button type="primary" @click="openAdd">新增地址</el-button>
    </div>

    <div v-loading="loading" class="addr__list">
      <div
        v-for="a in list"
        :key="a.id"
        class="addr-card"
        :class="{ 'addr-card--default': a.defaultStatus === 1 }"
      >
        <div class="addr-card__top">
          <span class="addr-card__name">{{ a.receiverName }}</span>
          <span class="addr-card__phone">{{ maskPhone(a.phone) }}</span>
          <span v-if="a.defaultStatus === 1" class="tag-default">默认</span>
        </div>
        <div class="addr-card__line">{{ fullAddress(a) }}</div>
        <div class="addr-card__actions">
          <el-button v-if="a.defaultStatus !== 1" link type="primary" @click="setDefault(a)">设为默认</el-button>
          <el-button link @click="openEdit(a)">编辑</el-button>
          <el-button link type="danger" @click="remove(a)">删除</el-button>
        </div>
      </div>
      <el-empty v-if="!loading && list.length === 0" description="还没有收货地址，快去添加一个吧" />
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑地址' : '新增地址'" width="460px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="收货人" required>
          <el-input v-model="form.receiverName" placeholder="请输入收货人姓名" />
        </el-form-item>
        <el-form-item label="手机号" required>
          <el-input v-model="form.phone" placeholder="请输入手机号" maxlength="11" />
        </el-form-item>
        <el-form-item label="所在地区" required>
          <div class="region">
            <el-input v-model="form.province" placeholder="省" />
            <el-input v-model="form.city" placeholder="市" />
            <el-input v-model="form.district" placeholder="区/县" />
          </div>
        </el-form-item>
        <el-form-item label="详细地址" required>
          <el-input v-model="form.detailAddress" type="textarea" :rows="2" placeholder="街道、门牌号等" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="defaultSwitch" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listAddresses, addAddress, updateAddress, deleteAddress, setDefaultAddress } from '@/apis/address'
import type { Address } from '@/types/order'

const list = ref<Address[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const defaultSwitch = ref(false)

const emptyForm = (): Address => ({
  receiverName: '',
  phone: '',
  province: '',
  city: '',
  district: '',
  detailAddress: '',
  defaultStatus: 0,
})
const form = reactive<Address>(emptyForm())

async function fetchList() {
  loading.value = true
  try {
    list.value = await listAddresses()
  } catch {
    ElMessage.error('地址加载失败')
  } finally {
    loading.value = false
  }
}

function maskPhone(p?: string) {
  if (!p) return ''
  return p.length >= 7 ? p.slice(0, 3) + '****' + p.slice(-4) : p
}
function fullAddress(a: Address) {
  return `${a.province || ''}${a.city || ''}${a.district || ''}${a.detailAddress || ''}`
}

function openAdd() {
  Object.assign(form, emptyForm())
  defaultSwitch.value = false
  dialogVisible.value = true
}
function openEdit(a: Address) {
  Object.assign(form, { ...a })
  defaultSwitch.value = a.defaultStatus === 1
  dialogVisible.value = true
}
async function save() {
  if (!form.receiverName?.trim()) return ElMessage.warning('请填写收货人')
  if (!/^1\d{10}$/.test(form.phone || '')) return ElMessage.warning('手机号格式不正确')
  if (!form.province || !form.city || !form.district || !form.detailAddress)
    return ElMessage.warning('请完整填写地区与详细地址')
  form.defaultStatus = defaultSwitch.value ? 1 : 0
  saving.value = true
  try {
    if (form.id) {
      await updateAddress({ ...form })
    } else {
      await addAddress({ ...form })
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    await fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}
async function setDefault(a: Address) {
  try {
    await setDefaultAddress(a.id!)
    ElMessage.success('已设为默认')
    await fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}
async function remove(a: Address) {
  try {
    await ElMessageBox.confirm(`确定删除「${a.receiverName}」的地址吗？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteAddress(a.id!)
    ElMessage.success('已删除')
    await fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

onMounted(fetchList)
</script>

<style scoped>
.addr {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px 16px 48px;
}
.addr__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.addr__title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  font-family: var(--mall-font-serif);
  color: var(--mall-text);
}
.addr__list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.addr-card {
  background: var(--mall-card);
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius);
  padding: 16px;
  box-shadow: var(--mall-shadow);
}
.addr-card--default {
  border-color: var(--mall-primary);
}
.addr-card__top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.addr-card__name {
  font-weight: 700;
  color: var(--mall-text);
}
.addr-card__phone {
  color: var(--mall-text-light);
  font-size: 13px;
}
.addr-card__line {
  color: var(--mall-text);
  font-size: 14px;
  line-height: 1.5;
  min-height: 42px;
}
.addr-card__actions {
  display: flex;
  gap: 4px;
  margin-top: 8px;
}
.region {
  display: flex;
  gap: 8px;
}
.region .el-input {
  flex: 1;
}
@media (max-width: 640px) {
  .addr__list {
    grid-template-columns: 1fr;
  }
}
</style>
