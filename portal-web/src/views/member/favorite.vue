<template>
  <div class="fav">
    <div class="fav__head">
      <h3 class="fav__title">我的收藏</h3>
      <span class="fav__count">共 {{ list.length }} 件</span>
    </div>

    <div v-loading="loading" class="fav__list">
      <article
        v-for="c in list"
        :key="c.id"
        class="fav-card"
        @click="goDetail(c.productId)"
      >
        <PicBox
          class="fav-card__pic"
          :pic="c.productPic"
          :name="c.productName"
          :ratio="1"
          :scale="0.94"
          ph-class="fav-card__ph"
        />
        <div class="fav-card__name">{{ c.productName }}</div>
        <div class="fav-card__price"><i>￥</i>{{ priceText(c.productPrice) }}</div>
        <div class="fav-card__actions" @click.stop>
          <el-button size="small" @click="goDetail(c.productId)">查看</el-button>
          <el-button size="small" type="danger" plain @click="remove(c)">取消收藏</el-button>
        </div>
      </article>
      <el-empty v-if="!loading && list.length === 0" description="还没有收藏的商品，去逛逛吧" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listCollects, removeCollect, type CollectItem } from '@/apis/favorite'
import PicBox from '@/components/PicBox.vue'

const router = useRouter()
const list = ref<CollectItem[]>([])
const loading = ref(false)

async function fetchList() {
  loading.value = true
  try {
    list.value = await listCollects()
  } catch {
    ElMessage.error('收藏列表加载失败')
  } finally {
    loading.value = false
  }
}

function priceText(v?: number | string | null) {
  const n = Number(v)
  if (!v || Number.isNaN(n)) return '--'
  return n.toFixed(2)
}
function goDetail(productId: number) {
  router.push({ path: '/product', query: { pid: productId } })
}
async function remove(c: CollectItem) {
  try {
    await ElMessageBox.confirm(`确定取消收藏「${c.productName}」吗？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  try {
    await removeCollect(c.productId)
    ElMessage.success('已取消收藏')
    await fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}

onMounted(fetchList)
</script>

<style scoped>
.fav {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px 16px 48px;
}
.fav__head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 16px;
}
.fav__title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  font-family: var(--mall-font-serif);
  color: var(--mall-text);
}
.fav__count {
  color: var(--mall-text-light);
  font-size: 13px;
}
.fav__list {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.fav-card {
  background: var(--mall-card);
  border-radius: var(--mall-radius);
  padding: 12px;
  cursor: pointer;
  transition: box-shadow 0.2s;
  box-shadow: var(--mall-shadow);
}
.fav-card:hover {
  box-shadow: 0 6px 16px rgba(192, 116, 79, 0.16);
}
.fav-card__pic {
  aspect-ratio: 1 / 1;
  border-radius: var(--mall-radius-sm);
  overflow: hidden;
  background: var(--mall-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}
.fav-card__pic img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.fav-card__ph {
  font-size: 36px;
  color: var(--mall-text-light);
}
.fav-card__name {
  margin-top: 8px;
  font-size: 14px;
  color: var(--mall-text);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  height: 40px;
}
.fav-card__price {
  margin-top: 6px;
  color: var(--mall-price);
  font-weight: 700;
}
.fav-card__price i {
  font-style: normal;
  font-size: 12px;
}
.fav-card__actions {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}
@media (max-width: 900px) {
  .fav__list {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (max-width: 640px) {
  .fav__list {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
