<template>
  <div class="search-page">
    <div class="result-head">
      <h2 class="result-title">搜索结果</h2>
      <div class="result-meta" v-if="keyword">
        <span>关键词：</span>
        <span class="kw" v-html="highlight(keyword)"></span>
        <span class="count">共 {{ total }} 件商品</span>
      </div>
      <div class="result-meta empty" v-else>请在上方搜索框输入关键词后搜索</div>
    </div>

    <div class="goods" v-loading="loading">
      <article
        v-for="p in list"
        :key="p.id"
        class="card"
        @click="openProduct(p.id)"
      >
        <div class="card__pic">
          <PicBox :pic="p.pic" :name="p.name" :ratio="1" :scale="0.92" ph-class="card__ph" />
          <span class="badge badge--self">自营</span>
          <span class="badge badge--free">包邮</span>
        </div>
        <div class="card__name" v-html="highlight(p.name)"></div>
        <div class="card__price-row">
          <span class="card__price"><i>￥</i>{{ priceText(p.lowestPrice) }}</span>
          <span class="card__sale">已售 {{ p.sale || 0 }} 件</span>
        </div>
      </article>

      <el-empty
        v-if="!loading && list.length === 0"
        description="没有找到相关商品，换个关键词试试"
      />
    </div>

    <div class="pager" v-if="total > pageSize">
      <el-pagination
        layout="prev, pager, next, total"
        :total="total"
        :current-page="pageNum"
        :page-size="pageSize"
        @current-change="onPageChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listProducts } from '@/apis/product'
import type { Product } from '@/types/product'
import PicBox from '@/components/PicBox.vue'

const list = ref<Product[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(12)
const keyword = ref('')
const loading = ref(false)

const route = useRoute()
const router = useRouter()

async function fetchList() {
  loading.value = true
  try {
    const data = await listProducts({
      keyword: keyword.value || undefined,
      pageNum: pageNum.value,
      pageSize: pageSize.value,
    })
    list.value = data.list
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function openProduct(id: number) {
  router.push({ path: '/product', query: { pid: id } })
}

function onPageChange(p: number) {
  pageNum.value = p
  fetchList()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function priceText(v?: number | null) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '--'
  return Number(v).toFixed(2)
}
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
function highlight(text?: string): string {
  const raw = text ?? ''
  const kw = keyword.value.trim()
  if (!kw) return escapeHtml(raw)
  let html = escapeHtml(raw)
  for (const token of kw.split(/\s+/).filter(Boolean)) {
    const escaped = escapeHtml(token)
    if (!escaped) continue
    const re = new RegExp(escaped.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')
    html = html.replace(re, (m) => `<mark>${m}</mark>`)
  }
  return html
}

// 关键词变化时（含从顶栏再次搜索 / 热搜跳转）刷新结果；无关键词则清空展示提示
watch(
  () => route.query.keyword,
  (val) => {
    keyword.value = typeof val === 'string' ? val.trim() : ''
    pageNum.value = 1
    if (keyword.value) fetchList()
    else {
      list.value = []
      total.value = 0
    }
  },
  { immediate: true }
)

onMounted(() => {
  // 初始进入若带关键词则拉取（immediate watch 已覆盖，这里兜底无需重复请求）
})
</script>

<style scoped>
.search-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 18px 16px 40px;
}

/* ---------- 结果头部（暖色生活方式风） ---------- */
.result-head {
  margin-bottom: 18px;
}
.result-title {
  font-family: var(--mall-font-serif);
  font-size: 26px;
  font-weight: 700;
  color: var(--mall-text);
  margin: 0 0 10px;
  letter-spacing: 1px;
}
.result-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--mall-text-light);
}
.result-meta .kw {
  color: var(--mall-primary);
  font-weight: 600;
}
.result-meta .count {
  color: var(--mall-text-regular);
}
.result-meta.empty {
  color: var(--mall-text-light);
}

/* ---------- 商品网格（与首页卡片视觉一致） ---------- */
.goods {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  min-height: 200px;
}
.card {
  position: relative;
  background: var(--mall-card);
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-lg);
  overflow: hidden;
  cursor: pointer;
  box-shadow: var(--mall-shadow);
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
}
.card:hover {
  transform: translateY(-4px);
  border-color: var(--mall-primary-soft);
  box-shadow: var(--mall-shadow-hover);
}
.card__pic {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  background: linear-gradient(160deg, #fdf8f2 0%, #f4e9dd 100%);
  overflow: hidden;
}
.card__pic img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  transition: transform 0.35s ease;
}
.card:hover .card__pic img {
  transform: scale(1.06);
}
.badge {
  position: absolute;
  z-index: 2;
  font-size: 11px;
  line-height: 1;
  padding: 4px 7px;
  border-radius: var(--mall-radius-sm);
  letter-spacing: 0.5px;
}
.badge--self {
  top: 10px;
  left: 10px;
  background: var(--mall-primary);
  color: #fff;
  font-family: var(--mall-font-serif);
}
.badge--free {
  right: 10px;
  bottom: 10px;
  background: rgba(255, 253, 251, 0.92);
  color: var(--mall-primary);
  border: 1px solid var(--mall-primary-soft);
}
.card__ph {
  font-family: var(--mall-font-serif);
  font-size: 48px;
  font-weight: 700;
  color: #e2d3c4;
}
.card__name {
  font-size: 14px;
  line-height: 1.45;
  color: var(--mall-text);
  padding: 0 12px;
  margin: 12px 0 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  height: 41px;
}
.card__price-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
  padding: 0 12px 14px;
}
.card__price {
  font-family: var(--mall-font-serif);
  color: var(--mall-price);
  font-weight: 700;
  font-size: 22px;
  line-height: 1;
  letter-spacing: 0.3px;
}
.card__price i {
  font-style: normal;
  font-size: 13px;
  font-weight: 400;
  margin-right: 1px;
}
.card__sale {
  font-size: 12px;
  color: var(--mall-text-light);
  flex-shrink: 0;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
}

/* 搜索关键词高亮 */
:deep(mark) {
  background: transparent;
  color: var(--mall-primary);
  font-weight: 600;
}
</style>
