<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-bar">
        <span>商品评价管理</span>
      </div>
    </template>

    <!-- 筛选区 -->
    <el-form :inline="true" class="filter-bar" @submit.prevent>
      <el-form-item label="商品ID">
        <el-input
          v-model="filterProductId"
          placeholder="可选"
          clearable
          style="width: 140px"
        />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filterStatus" placeholder="全部" clearable style="width: 130px">
          <el-option :value="0" label="待审核" />
          <el-option :value="1" label="已通过" />
          <el-option :value="2" label="已驳回" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input
          v-model="keyword"
          placeholder="会员昵称 / 商品名"
          clearable
          style="width: 180px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 主表格 -->
    <el-table :data="list" v-loading="loading" border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="商品" min-width="200">
        <template #default="{ row }">
          <div class="prod">
            <img v-if="row.productPic" :src="row.productPic" class="prod-img" alt="" />
            <span class="prod-name">{{ row.productName || '-' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="会员" width="120">
        <template #default="{ row }">
          <span v-if="row.anonymous === 1">匿名用户</span>
          <span v-else>{{ row.nickname || '会员' + row.memberId }}</span>
        </template>
      </el-table-column>
      <el-table-column label="评分" width="130">
        <template #default="{ row }">
          <el-rate :model-value="row.star" disabled />
        </template>
      </el-table-column>
      <el-table-column label="内容" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.content || '（无文字）' }}</template>
      </el-table-column>
      <el-table-column label="晒图" width="90" align="center">
        <template #default="{ row }">
          <span v-if="commentPics(row.pics).length">{{ commentPics(row.pics).length }} 张</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)">{{ COMMENT_STATUS_TEXT[row.status] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createTime" label="提交时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openView(row)">查看</el-button>
          <el-button
            v-if="row.status === 0"
            size="small"
            link
            type="success"
            @click="audit(row, 1)"
          >通过</el-button>
          <el-button
            v-if="row.status === 0"
            size="small"
            link
            type="warning"
            @click="audit(row, 2)"
          >驳回</el-button>
          <el-button size="small" link type="info" @click="openReply(row)">回复</el-button>
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

    <!-- 查看详情弹窗 -->
    <el-dialog v-model="viewVisible" title="评价详情" width="620px">
      <div v-if="current" class="detail">
        <div class="detail-head">
          <img v-if="current.productPic" :src="current.productPic" class="detail-img" alt="" />
          <div>
            <div class="detail-name">{{ current.productName || '-' }}</div>
            <div class="detail-sub">订单号：{{ current.orderSn }} · 会员ID：{{ current.memberId }}</div>
            <el-rate :model-value="current.star" disabled style="margin-top: 6px" />
          </div>
        </div>
        <div class="detail-content">{{ current.content || '（无文字评价）' }}</div>
        <div v-if="commentPics(current.pics).length" class="detail-pics">
          <img
            v-for="(p, i) in commentPics(current.pics)"
            :key="i"
            :src="p"
            class="detail-pic"
            alt=""
          />
        </div>
        <div v-if="current.replyContent" class="detail-reply">
          <strong>商家回复：</strong>{{ current.replyContent }}
          <span class="detail-reply-time" v-if="current.updateTime">（{{ fmtTime(current.updateTime) }}）</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="viewVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 回复弹窗 -->
    <el-dialog v-model="replyVisible" title="回复评价" width="520px">
      <el-input
        v-model="replyContent"
        type="textarea"
        :rows="3"
        maxlength="500"
        show-word-limit
        placeholder="请输入回复内容"
      />
      <template #footer>
        <el-button @click="replyVisible = false">取消</el-button>
        <el-button type="primary" :loading="replying" @click="submitReply">确定回复</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { listComments, auditComment, replyComment, deleteComment } from '@/apis/comment'
import { COMMENT_STATUS_TEXT, commentPics, type CommentListItem } from '@/types/comment'
import { ElMessage, ElMessageBox } from 'element-plus'

const list = ref<CommentListItem[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const loading = ref(false)

const filterProductId = ref<string>('')
const filterStatus = ref<number | undefined>(undefined)
const keyword = ref('')

const viewVisible = ref(false)
const current = ref<CommentListItem | null>(null)
const replyVisible = ref(false)
const replyContent = ref('')
const replying = ref(false)

function statusTagType(status: number): 'warning' | 'success' | 'info' | 'danger' {
  if (status === 0) return 'warning'
  if (status === 1) return 'success'
  if (status === 2) return 'danger'
  return 'info'
}
function fmtTime(t?: string) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}

async function loadData() {
  loading.value = true
  try {
    const params: {
      pageNum: number
      pageSize: number
      productId?: number
      status?: number
      keyword?: string
    } = {
      pageNum: pageNum.value,
      pageSize: pageSize.value,
    }
    const pid = Number(filterProductId.value)
    if (filterProductId.value.trim() && pid > 0) params.productId = pid
    if (filterStatus.value !== undefined && filterStatus.value !== null) {
      params.status = filterStatus.value
    }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    const data = await listComments(params)
    list.value = data.list
    total.value = data.total
  } catch (error) {
    console.error('加载评价列表失败:', error)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pageNum.value = 1
  loadData()
}
function handleReset() {
  filterProductId.value = ''
  filterStatus.value = undefined
  keyword.value = ''
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

function openView(row: CommentListItem) {
  current.value = row
  viewVisible.value = true
}

async function audit(row: CommentListItem, status: number) {
  try {
    await auditComment(row.id, status)
    ElMessage.success(status === 1 ? '已通过' : '已驳回')
    loadData()
  } catch (error) {
    console.error('审核失败:', error)
  }
}

function openReply(row: CommentListItem) {
  current.value = row
  replyContent.value = row.replyContent || ''
  replyVisible.value = true
}
async function submitReply() {
  if (!current.value) return
  if (!replyContent.value.trim()) {
    ElMessage.warning('请输入回复内容')
    return
  }
  replying.value = true
  try {
    await replyComment(current.value.id, replyContent.value.trim())
    ElMessage.success('回复成功')
    replyVisible.value = false
    loadData()
  } catch (error) {
    console.error('回复失败:', error)
  } finally {
    replying.value = false
  }
}

async function handleDelete(row: CommentListItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除该评价（ID=${row.id}）吗？此操作不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await deleteComment(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    console.error('删除失败:', error)
  }
}

loadData()
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
.prod {
  display: flex;
  align-items: center;
  gap: 8px;
}
.prod-img {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 4px;
  flex: 0 0 40px;
}
.prod-name {
  font-size: 13px;
  color: var(--color-text-primary);
}
.detail-head {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 14px;
}
.detail-img {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: 6px;
  flex: 0 0 64px;
}
.detail-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}
.detail-sub {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.detail-content {
  font-size: 14px;
  color: var(--color-text-primary);
  line-height: 1.7;
  background: var(--color-background-secondary);
  border-radius: 8px;
  padding: 10px 12px;
}
.detail-pics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.detail-pic {
  width: 88px;
  height: 88px;
  object-fit: cover;
  border-radius: 6px;
}
.detail-reply {
  margin-top: 12px;
  font-size: 13px;
  color: var(--color-text-primary);
  background: var(--color-background-tertiary);
  border-radius: 8px;
  padding: 10px 12px;
}
.detail-reply-time {
  color: var(--color-text-tertiary);
  margin-left: 6px;
}
</style>
