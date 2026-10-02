<template>
  <div class="home">
    <!-- 热搜词：点击即搜索（搜索框统一由顶栏提供） -->
    <div class="hot">
      <span class="hot__label">热搜</span>
      <span
        v-for="w in hotWords"
        :key="w"
        class="hot__word"
        @click="searchByWord(w)"
      >{{ w }}</span>
    </div>

    <!-- 主视觉：Banner + 促销卡 -->
    <div class="hero">
      <div class="hero__banner">
        <div class="hero__banner-text">
          <h2>新品首发</h2>
          <p>严选好物 · 正品保障 · 极速发货</p>
          <button class="hero__cta" type="button" @click="scrollToGoods">立即选购</button>
        </div>
      </div>
      <div class="hero__side">
        <div class="promo promo--a">
          <div class="promo__title">新人专享</div>
          <div class="promo__sub">首单立减 · 限时领取</div>
        </div>
        <div class="promo promo--b">
          <div class="promo__title">品质好物</div>
          <div class="promo__sub">七天无理由退换</div>
        </div>
      </div>
    </div>

    <!-- 分类导航：原为左侧竖栏，高度与商品对不齐；改到 hero 下方横向导航，商品全宽铺开 -->
    <nav class="cat-nav">
      <div class="cat-nav__row">
        <span
          class="cat-nav__item"
          :class="{ active: selectedCategoryId == null }"
          @click="selectCategory(null)"
        >全部</span>
        <span
          v-for="c in categories"
          :key="c.id"
          class="cat-nav__item"
          :class="{ expanded: expandedTopId === c.id }"
          @click="toggleTop(c.id)"
        >
          <img v-if="isImgUrl(c.icon)" class="cat-nav__ico" :src="c.icon" alt="" />{{ c.name }}
        </span>
      </div>
      <div v-if="activeChildren.length" class="cat-nav__sub">
        <span
          v-for="sub in activeChildren"
          :key="sub.id"
          class="cat-nav__sub-item"
          :class="{ active: selectedCategoryId === sub.id }"
          @click="selectCategory(sub.id)"
        >{{ sub.name }}</span>
      </div>
    </nav>

    <section class="main" ref="goodsRef">
        <!-- 品牌筛选行 -->
        <div class="filter">
          <span class="filter__label">品牌</span>
          <span
            class="filter__opt"
            :class="{ active: selectedBrandId == null }"
            @click="selectBrand(null)"
          >全部</span>
          <span
            v-for="b in brands"
            :key="b.id"
            class="filter__opt"
            :class="{ active: selectedBrandId === b.id }"
            @click="selectBrand(b.id)"
          >{{ b.name }}</span>
          <span v-if="brands.length === 0" class="filter__empty">该分类下暂无品牌</span>
          <button v-if="hasFilter" class="filter__reset" type="button" @click="resetFilter">重置筛选</button>
        </div>

        <!-- 商品网格 -->
        <div class="goods" v-loading="loading">
          <article
            v-for="p in list"
            :key="p.id"
            class="card"
            @click="openDetail(p.id)"
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

          <el-empty v-if="!loading && list.length === 0" description="暂无相关商品" />
        </div>

        <div class="pager">
          <el-pagination
            layout="prev, pager, next, total"
            :total="total"
            :current-page="pageNum"
            :page-size="pageSize"
            @current-change="onPageChange"
          />
        </div>
      </section>

    <!-- 商品详情抽屉 -->
    <el-drawer v-model="drawer" title="商品详情" size="680px">
      <template v-if="detail && detail.product">
        <!-- 商品详情：左主图 + 右信息 两栏；放大预览浮层覆盖在右栏之上 -->
        <div class="d-wrap">
          <div class="d-media" :style="{ width: stageBox.w + 'px' }">
            <div
              class="zoom__main"
              ref="mainRef"
              :style="stageStyle"
              @mouseenter="zoomShow = true"
              @mouseleave="zoomShow = false"
              @mousemove="onZoomMove"
            >
              <span v-if="!detail.product.pic" class="card__ph">{{ firstChar(detail.product.name) }}</span>
              <div class="zoom__lens" v-show="zoomShow && detail.product.pic" :style="lensStyle"></div>
            </div>

            <!-- 左栏信息卡：用真实商品数据填满下方留白 -->
            <ul class="d-facts">
              <li>
                <span>货号</span>
                <b>{{ detail.product.productSn || '-' }}</b>
              </li>
              <li>
                <span>已售</span>
                <b>{{ detail.product.sale || 0 }} 件</b>
              </li>
              <li>
                <span>库存</span>
                <b>{{ totalStock }} 件</b>
              </li>
              <li>
                <span>已选</span>
                <b class="d-facts__pick">{{ pickedSpecText || '尚未选择规格' }}</b>
              </li>
            </ul>
          </div>

          <div class="d-info">
            <h3 class="detail-name" v-html="highlight(detail.product.name)"></h3>
            <div class="detail-price-box">
              <template v-if="selectedSku">
                <span class="detail-price-label">单价</span>
                <span class="detail-price-num"><i>￥</i>{{ priceText(selectedSku.price) }}</span>
                <span class="detail-stock">库存 {{ selectedSku.stock }}</span>
              </template>
              <template v-else-if="detail.product.lowestPrice != null">
                <span class="detail-price-label">最低只需</span>
                <span class="detail-price-num"><i>￥</i>{{ priceText(detail.product.lowestPrice) }}</span>
              </template>
              <span v-else class="detail-stock">暂无报价</span>
            </div>

            <p class="sec-label">选择规格<i>共 {{ detail.skus.length }} 个规格</i></p>
            <div class="sku-list">
              <div
                v-for="s in detail.skus"
                :key="s.id"
                class="sku-item"
                :class="{ active: selectedSkuId === s.id, disabled: (s.stock || 0) <= 0 }"
                @click="selectSku(s)"
              >
                <div class="sku-item__main">
                  <span class="sku-spec">{{ formatSpec(s.spData) || s.skuCode }}</span>
                  <span class="sku-price">￥{{ priceText(s.price) }}</span>
                </div>
                <div class="sku-stock" :class="{ 'sku-stock--empty': (s.stock || 0) <= 0 }">
                  {{ (s.stock || 0) > 0 ? `库存 ${s.stock}` : '暂时缺货' }}
                </div>
              </div>
            </div>

            <div class="buy-qty">
              <span class="qty-label">数量</span>
              <el-input-number v-model="quantity" :min="1" :max="selectedSku ? (selectedSku.stock || 1) : 99" />
            </div>

            <div class="buy-actions">
              <el-button :disabled="!selectedSku" :loading="cartAdding" @click="addToCart">加入购物车</el-button>
              <el-button type="primary" :disabled="!selectedSku" @click="buyNow">立即购买</el-button>
              <el-button
                :loading="collectLoading"
                :type="collected ? 'warning' : 'default'"
                @click="toggleCollect"
              >
                <el-icon><Star /></el-icon>{{ collected ? '已收藏' : '收藏' }}
              </el-button>
            </div>
          </div>

          <!-- 放大预览浮层：hover 时浮于右栏信息之上 -->
          <div class="zoom__result" v-show="zoomShow && detail.product.pic" :style="previewStyle"></div>
        </div>

        <el-divider>用户评价</el-divider>
        <div class="reviews" v-loading="commentsLoading">
          <div v-if="commentStats" class="rev-stats">
            <span class="rev-avg"><b>{{ commentStats.avgStar }}</b> 分</span>
            <span class="rev-total">共 {{ commentStats.total }} 条评价</span>
          </div>
          <div v-for="c in productComments" :key="c.id" class="rev-item">
            <div class="rev-head">
              <span class="rev-user">{{ c.anonymous === 1 ? '匿名用户' : (c.nickname || '用户') }}</span>
              <el-rate :model-value="c.star" disabled size="small" />
              <span class="rev-time" v-if="c.createTime">{{ fmtCommentTime(c.createTime) }}</span>
            </div>
            <div class="rev-content">{{ c.content || '（该用户未填写文字评价）' }}</div>
            <div v-if="toPics(c.pics).length" class="rev-pics">
              <img v-for="(p, i) in toPics(c.pics)" :key="i" :src="p" class="rev-pic" alt="" />
            </div>
            <div v-if="c.replyContent" class="rev-reply">商家回复：{{ c.replyContent }}</div>
          </div>
          <el-empty v-if="!commentsLoading && (!commentStats || commentStats.total === 0)" description="暂无评价" />
        </div>

        <el-divider>相关推荐</el-divider>
        <div class="similar" v-loading="similarLoading">
          <article
            v-for="p in similarList"
            :key="p.id"
            class="similar__card"
            @click="openDetail(p.id)"
          >
            <div class="similar__pic">
              <PicBox :pic="p.pic" :name="p.name" :ratio="1" :scale="0.94" ph-class="card__ph" />
            </div>
            <div class="similar__name">{{ p.name }}</div>
            <div class="similar__price-row">
              <span class="similar__price"><i>￥</i>{{ priceText(p.lowestPrice) }}</span>
              <span class="similar__sale">已售 {{ p.sale || 0 }}</span>
            </div>
          </article>
          <el-empty
            v-if="!similarLoading && similarList.length === 0"
            description="暂无相关商品"
            :image-size="60"
          />
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useLoginGate } from '@/stores/loginGate'
import { ElMessage, ElNotification } from 'element-plus'
import { Star } from '@element-plus/icons-vue'
import { listProducts, getProduct, getSimilarProducts } from '@/apis/product'
import { listCategories } from '@/apis/category'
import { listBrands } from '@/apis/brand'
import { addCart } from '@/apis/cart'
import { addGuestCart } from '@/utils/guestCart'
import { getCommentStats, listProductComments } from '@/apis/comment'
import { addCollect, removeCollect, isCollected } from '@/apis/favorite'
import { formatSpec } from '@/utils/spec'
import { picMeta, fullCrop, type PicCrop } from '@/utils/picTrim'
import PicBox from '@/components/PicBox.vue'
import type { Product, ProductDetailVO, Sku } from '@/types/product'
import type { CategoryNode } from '@/types/category'
import type { Brand } from '@/types/brand'
import { toPics, type CommentStats, type ProductCommentVO } from '@/types/comment'

const list = ref<Product[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const loading = ref(false)

const categories = ref<CategoryNode[]>([])
const brands = ref<Brand[]>([])
const selectedCategoryId = ref<number | null>(null)
const selectedBrandId = ref<number | null>(null)

const hotWords = ['手机', '耳机', '笔记本', '智能手表', '充电宝', '显示器', '音响', '数据线']

const goodsRef = ref<HTMLElement>()

const hasFilter = computed(
  () => selectedCategoryId.value != null || selectedBrandId.value != null || keyword.value.trim() !== ''
)

// 横向导航：顶级分类（父标题）只负责「展开/收起」二级分类子行，不在前端触发商品查询。
// 原因：后端 ProductController.list 按 categoryId 精确匹配，父级 id 下没有直属商品，点了也是空；
// 因此只允许点叶子子分类（它们挂有商品）发起查询，父标题点击仅展开子行。
const expandedTopId = ref<number | null>(null)
const activeChildren = computed<CategoryNode[]>(() => {
  const top = categories.value.find((c) => c.id === expandedTopId.value)
  return top ? top.children || [] : []
})
function toggleTop(id: number) {
  expandedTopId.value = expandedTopId.value === id ? null : id
}

const drawer = ref(false)
const detail = ref<ProductDetailVO | null>(null)
const selectedSkuId = ref<number | null>(null)
const quantity = ref(1)
const cartAdding = ref(false)

// 商品详情放大镜：鼠标在舞台上移动，半透明遮罩层(lens)跟随，旁边浮层同步显示该区域放大图。
// 舞台渲染的是「商品图内容盒」（去掉白边后那块），所以遮罩坐标 → 原图像素的换算全部基于内容盒，
// 既不会出现图小框大的留白，各比例图片放大也对得齐。
const STAGE_MAX_W = 300 // 舞台最大宽
const STAGE_MAX_H = 336 // 舞台最大高（竖图按此限高，避免左栏被拉太长）
const LENS = 120 // 遮罩层边长(px)
const PREVIEW = 300 // 放大预览区边长(px)，与 .zoom__result 一致；放大倍率 = PREVIEW / LENS = 2.5x
const mainRef = ref<HTMLElement | null>(null)
const zoomShow = ref(false)
const lensStyle = ref<Record<string, string>>({})
const resultStyle = ref<Record<string, string>>({})
const crop = ref<PicCrop>(fullCrop()) // 当前商品图内容盒
const natW = ref(0) // 原图宽（px）
const natH = ref(0) // 原图高（px）

/** 打开详情时确定舞台图源：优先用离线裁剪元数据，未收录则退回整图（异步探针取原图尺寸） */
function applyStageSource(pic?: string) {
  const meta = picMeta(pic)
  if (meta) {
    crop.value = meta
    natW.value = meta.W
    natH.value = meta.H
    return
  }
  crop.value = fullCrop()
  natW.value = 0
  natH.value = 0
  if (pic) {
    const probe = new Image()
    probe.onload = () => {
      natW.value = probe.naturalWidth
      natH.value = probe.naturalHeight
    }
    probe.src = pic
  }
}

// 内容盒宽高比：决定舞台形状（横图矮、竖图窄），没有任何"图小框大"
const stageAr = computed(() => {
  const c = crop.value
  if (natW.value > 0 && natH.value > 0) return (c.tw * natW.value) / (c.th * natH.value)
  return 1.25
})
// 舞台尺寸：内容盒按比例装进 300 x 336 的框
const stageBox = computed(() => {
  const ar = stageAr.value > 0 ? stageAr.value : 1
  let w = STAGE_MAX_W
  let h = w / ar
  if (h > STAGE_MAX_H) {
    h = STAGE_MAX_H
    w = h * ar
  }
  return { w: Math.round(w), h: Math.round(h) }
})
// 舞台样式：背景图按内容盒放大并位移，让内容盒正好铺满舞台（single-axis size + % 定位，天然自适应任何宽度）
const stageStyle = computed<Record<string, string>>(() => {
  const box = stageBox.value
  const c = crop.value
  const pic = detail.value?.product?.pic || ''
  const style: Record<string, string> = { width: box.w + 'px', height: box.h + 'px' }
  if (!pic) return style
  style.backgroundImage = `url("${pic}")`
  style.backgroundSize = `${(100 / c.tw).toFixed(3)}% auto`
  const px = c.tw >= 0.999 ? 0 : (c.x0 / (1 - c.tw)) * 100
  const py = c.th >= 0.999 ? 0 : (c.y0 / (1 - c.th)) * 100
  style.backgroundPosition = `${px.toFixed(3)}% ${py.toFixed(3)}%`
  style.backgroundRepeat = 'no-repeat'
  return style
})
// 放大预览浮层：紧贴舞台右侧（舞台宽度随商品图变化，故这里动态定位）
const previewStyle = computed<Record<string, string>>(() => ({
  left: stageBox.value.w + 22 + 'px',
  ...resultStyle.value
}))

function onZoomMove(e: MouseEvent) {
  const el = mainRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const w = rect.width
  const h = rect.height
  const W = natW.value
  const H = natH.value
  const c = crop.value
  if (!w || !h || !W || !H) return
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  const left = Math.max(0, Math.min(mx - LENS / 2, w - LENS))
  const top = Math.max(0, Math.min(my - LENS / 2, h - LENS))
  lensStyle.value = {
    left: left + 'px',
    top: top + 'px',
    width: LENS + 'px',
    height: LENS + 'px'
  }
  // 遮罩中心 → 原图像素坐标
  const ix = (c.x0 + ((left + LENS / 2) / w) * c.tw) * W
  const iy = (c.y0 + ((top + LENS / 2) / h) * c.th) * H
  // 倍率：遮罩覆盖的 LENS 个舞台像素 → 铺满 PREVIEW 见方，换算成"预览px / 原图px"
  const M = PREVIEW / ((LENS * c.tw * W) / w)
  resultStyle.value = {
    backgroundImage: `url("${detail.value?.product?.pic || ''}")`,
    backgroundSize: `${W * M}px ${H * M}px`,
    backgroundPosition: `${PREVIEW / 2 - ix * M}px ${PREVIEW / 2 - iy * M}px`,
    backgroundRepeat: 'no-repeat'
  }
}
const totalStock = computed(() => (detail.value?.skus || []).reduce((sum, s) => sum + (s.stock || 0), 0))
const pickedSpecText = computed(() => {
  const s = detail.value?.skus?.find((x) => x.id === selectedSkuId.value)
  if (!s) return ''
  return formatSpec(s.spData) || s.skuCode || ''
})

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 收藏状态（详情抽屉内切换）
const collected = ref(false)
const collectLoading = ref(false)

const selectedSku = computed<Sku | undefined>(() =>
  detail.value?.skus.find((s) => s.id === selectedSkuId.value)
)

// 商品详情页评价区
const commentStats = ref<CommentStats | null>(null)
const productComments = ref<ProductCommentVO[]>([])
const commentsLoading = ref(false)

// 商品详情页"相关推荐"（猜你喜欢-详情页版）
const similarList = ref<Product[]>([])
const similarLoading = ref(false)

async function fetchList() {
  loading.value = true
  try {
    const data = await listProducts({
      keyword: keyword.value || undefined,
      categoryId: selectedCategoryId.value ?? undefined,
      brandId: selectedBrandId.value ?? undefined,
      pageNum: pageNum.value,
      pageSize: pageSize.value,
    })
    list.value = data.list
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function fetchCategories() {
  categories.value = await listCategories()
}

async function fetchBrands() {
  brands.value = await listBrands(selectedCategoryId.value ?? undefined)
}

function selectCategory(id: number | null) {
  selectedCategoryId.value = id
  selectedBrandId.value = null
  pageNum.value = 1
  if (id == null) {
    expandedTopId.value = null
  } else {
    // 选中的若是叶子子分类，自动展开其所属父级，方便看到高亮
    const parent = categories.value.find((c) => (c.children || []).some((s) => s.id === id))
    expandedTopId.value = parent ? parent.id : id
  }
  fetchBrands()
  fetchList()
}

function selectBrand(id: number | null) {
  selectedBrandId.value = id
  pageNum.value = 1
  fetchList()
}

function resetFilter() {
  selectedCategoryId.value = null
  selectedBrandId.value = null
  keyword.value = ''
  pageNum.value = 1
  expandedTopId.value = null
  fetchBrands()
  fetchList()
}

function onPageChange(p: number) {
  pageNum.value = p
  fetchList()
}

// 热搜词：跳转到独立搜索结果页（与顶栏搜索一致），由 Search 页读 query.keyword 展示
function searchByWord(word: string) {
  router.push({ path: '/search', query: { keyword: word } })
}

function scrollToGoods() {
  goodsRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function openDetail(id: number) {
  const data = await getProduct(id)
  detail.value = data
  applyStageSource(data.product?.pic) // 按该商品图的内容盒重建舞台，避免白边留白
  selectedSkuId.value = null
  quantity.value = 1
  drawer.value = true
  loadComments(id)
  loadSimilar(id)
  // 已登录时查询是否已收藏（未登录直接视为未收藏，避免无谓报错）
  collected.value = false
  if (userStore.token) {
    try {
      collected.value = await isCollected(id)
    } catch {
      collected.value = false
    }
  }
}

// 拉取商品评价统计 + 列表（公开接口，仅返回审核通过 status=1）
async function loadComments(productId: number) {
  commentsLoading.value = true
  commentStats.value = null
  productComments.value = []
  try {
    const [stats, list] = await Promise.all([
      getCommentStats(productId),
      listProductComments(productId, 1, 10),
    ])
    commentStats.value = stats
    productComments.value = list.list
  } catch {
    // 评价接口异常不影响商品详情主流程
  } finally {
    commentsLoading.value = false
  }
}

// 相关推荐：同分类商品（后端已按销量倒序、排除自身）
async function loadSimilar(productId: number) {
  similarLoading.value = true
  similarList.value = []
  try {
    similarList.value = await getSimilarProducts(productId, 8)
  } catch {
    // 推荐接口异常不影响商品详情主流程
  } finally {
    similarLoading.value = false
  }
}

// 评价时间格式化：保留到「月-日 时:分」
function fmtCommentTime(t?: string): string {
  if (!t) return ''
  const d = new Date(t.replace(/-/g, '/'))
  if (Number.isNaN(d.getTime())) return t
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 分类 icon 语义是图片 URL：只有像 URL 才渲染成图片，脏数据（如字面量 "string"）一律忽略
function isImgUrl(u?: string): boolean {
  return !!u && /^(https?:)?\/\//i.test(u)
}

function firstChar(name?: string) {
  return name && name.trim() ? name.trim().charAt(0) : '商'
}

function priceText(v?: number | null) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '--'
  return Number(v).toFixed(2)
}

function selectSku(s: Sku) {
  if ((s.stock || 0) <= 0) return
  selectedSkuId.value = s.id
}

async function addToCart() {
  if (!selectedSku.value) {
    ElMessage.warning('请先选择规格')
    return
  }
  cartAdding.value = true
  try {
    // 未登录：写入本地暂存车（带商品快照，供购物车页直接渲染），登录后自动并入
    if (!userStore.token) {
      addGuestCart(selectedSku.value.id, quantity.value, {
        productId: detail.value?.product.id,
        name: detail.value?.product.name,
        pic: detail.value?.product.pic,
        price: selectedSku.value.price,
        spData: selectedSku.value.spData,
        skuCode: selectedSku.value.skuCode,
      })
      ElMessage.success('加入购物车成功')
      return
    }
    await addCart(selectedSku.value.id, quantity.value)
    ElNotification({
      title: '已加入购物车',
      message: '点击前往购物车结算',
      type: 'success',
      duration: 2000,
      onClick: () => router.push('/cart'),
    })
  } finally {
    cartAdding.value = false
  }
}

function buyNow() {
  if (!selectedSku.value || !detail.value) {
    ElMessage.warning('请先选择规格')
    return
  }
  router.push({
    path: '/order/confirm',
    query: {
      productId: detail.value.product.id,
      skuId: selectedSku.value.id,
      quantity: quantity.value,
    },
  })
}

// 收藏 / 取消收藏（需登录）
async function toggleCollect() {
  if (!detail.value) return
  const id = detail.value.product.id
  collectLoading.value = true
  try {
    if (collected.value) {
      await removeCollect(id)
      collected.value = false
      ElMessage.success('已取消收藏')
    } else {
      await addCollect(id)
      collected.value = true
      ElMessage.success('已收藏')
    }
  } catch (e: any) {
    if (!userStore.token) {
      // 未登录：弹窗引导登录（不硬跳登录页）
      useLoginGate().require(route.fullPath)
    } else {
      ElMessage.error(e?.message || '操作失败')
    }
  } finally {
    collectLoading.value = false
  }
}

// 高亮：对关键词做 HTML 转义后再包裹 <mark>，避免 XSS；按空白拆分多个词分别高亮
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

onMounted(() => {
  const q = route.query.keyword
  if (typeof q === 'string' && q.trim()) {
    keyword.value = q
  }
  fetchCategories()
  fetchBrands()
  fetchList()
  // 从「我的收藏」点进来：带 pid 直接打开商品详情抽屉
  const pid = route.query.pid
  if (typeof pid === 'string' && pid) {
    openDetail(Number(pid))
  }
})

// 顶栏搜索 / 热搜词跳转：query.keyword 变化时同步刷新列表
watch(
  () => route.query.keyword,
  (val) => {
    const kw = typeof val === 'string' ? val.trim() : ''
    keyword.value = kw
    pageNum.value = 1
    fetchList()
  }
)

// 从「我的收藏」点进来：query.pid 变化时直接打开对应商品详情
watch(
  () => route.query.pid,
  (val) => {
    if (typeof val === 'string' && val) {
      openDetail(Number(val))
    }
  }
)
</script>

<style scoped>
.home {
  max-width: 1200px;
  margin: 0 auto;
  padding: 14px 16px 40px;
}

/* ---------- 热搜词 ---------- */
.hot {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 16px;
  margin-bottom: 12px;
  font-size: 13px;
}
.hot__label {
  color: var(--mall-text-light);
  font-family: var(--mall-font-serif);
  letter-spacing: 1px;
}
.hot__word {
  color: var(--mall-text-regular);
  cursor: pointer;
}
.hot__word:hover {
  color: var(--mall-primary);
}

/* ---------- 主视觉 ---------- */
.hero {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}
.hero__banner {
  flex: 1;
  min-width: 0;
  height: 190px;
  border-radius: var(--mall-radius-lg);
  background: linear-gradient(120deg, #f8ece4 0%, #f0d8c8 100%);
  display: flex;
  align-items: center;
  padding: 0 48px;
  overflow: hidden;
}
.hero__banner h2 {
  font-family: var(--mall-font-serif);
  font-size: 34px;
  margin: 0 0 10px;
  color: var(--mall-primary);
  letter-spacing: 2px;
}
.hero__banner p {
  margin: 0 0 18px;
  color: #9a7a6c;
  font-size: 14px;
}
.hero__cta {
  border: none;
  background: var(--mall-primary);
  color: #fff;
  padding: 9px 26px;
  border-radius: var(--mall-radius);
  font-size: 14px;
  cursor: pointer;
}
.hero__cta:hover {
  background: var(--mall-primary-dark);
}
.hero__side {
  width: 230px;
  flex: 0 0 230px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.promo {
  flex: 1;
  border-radius: var(--mall-radius);
  padding: 0 18px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.promo--a {
  background: #eef3e8;
}
.promo--b {
  background: #f6e6dc;
}
.promo__title {
  font-family: var(--mall-font-serif);
  font-size: 16px;
  font-weight: 700;
  color: var(--mall-text);
  margin-bottom: 4px;
}
.promo__sub {
  font-size: 12px;
  color: var(--mall-text-light);
}

/* ---------- 分类横向导航 ---------- */
.cat-nav {
  background: var(--mall-card);
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius);
  padding: 10px 14px;
  margin-bottom: 14px;
}
.cat-nav__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 6px;
}
.cat-nav__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--mall-text-regular);
  cursor: pointer;
  padding: 6px 12px;
  border-radius: var(--mall-radius);
  transition: color 0.15s, background 0.15s;
}
.cat-nav__item:hover {
  color: var(--mall-primary);
}
.cat-nav__item.active {
  color: #fff;
  background: var(--mall-primary);
  font-weight: 600;
}
/* 父标题展开态：浅陶土底，表示「当前分组已展开」（不直接查商品） */
.cat-nav__item.expanded {
  color: var(--mall-primary);
  background: var(--mall-primary-soft);
  font-weight: 600;
}
.cat-nav__ico {
  width: 16px;
  height: 16px;
  object-fit: contain;
}
.cat-nav__sub {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 4px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--mall-border);
}
.cat-nav__sub-item {
  font-size: 12px;
  color: var(--mall-text-light);
  cursor: pointer;
  padding: 3px 10px;
  border-radius: var(--mall-radius);
  transition: color 0.15s, background 0.15s;
}
.cat-nav__sub-item:hover,
.cat-nav__sub-item.active {
  color: var(--mall-primary);
  background: var(--mall-primary-soft);
}

.main {
  width: 100%;
}

.filter {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  background: var(--mall-card);
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius);
  padding: 11px 14px;
  margin-bottom: 14px;
  font-size: 13px;
}
.filter__label {
  color: var(--mall-text-light);
}
.filter__opt {
  cursor: pointer;
  color: var(--mall-text-regular);
}
.filter__opt:hover {
  color: var(--mall-primary);
}
.filter__opt.active {
  color: var(--mall-primary);
  font-weight: 600;
}
.filter__empty {
  color: var(--mall-text-light);
}
.filter__reset {
  margin-left: auto;
  border: 1px solid var(--mall-border);
  background: #fff;
  color: var(--mall-text-regular);
  border-radius: var(--mall-radius);
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}
.filter__reset:hover {
  color: var(--mall-primary);
  border-color: var(--mall-primary);
}

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
/* 图片角标：自营（实心暖）+ 包邮（浅底描边） */
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

/* ---------- 详情抽屉 ---------- */
.detail-img {
  position: relative;
  width: 100%;
  min-height: 240px;
  background: linear-gradient(160deg, #fdf8f2 0%, #f4e9dd 100%);
  border-radius: var(--mall-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  margin-bottom: 16px;
  padding: 12px;
}
.detail-img img {
  max-width: 100%;
  max-height: 420px;
  width: auto;
  height: auto;
  object-fit: contain;
  border-radius: var(--mall-radius-sm);
}

/* ---------- 商品放大镜 ---------- */
.d-wrap {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr); /* 左栏宽度 = 舞台宽度（随商品图内容盒变化） */
  gap: 22px;
  align-items: start;
  margin-bottom: 16px;
}
.d-media {
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: sticky;
  top: 0;
}
.d-info {
  min-width: 0;
}
.zoom__main {
  position: relative;
  flex-shrink: 0;
  border-radius: var(--mall-radius-lg);
  overflow: hidden;
  cursor: crosshair;
  /* 尺寸与背景图由 stageStyle 注入：舞台 = 商品图内容盒，内容盒铺满舞台，四周无白边 */
  background-color: var(--mall-stage);
  background-repeat: no-repeat;
  /* 与放大预览同色、同混合：残留的白底会"融"成暖底色，不再是一大片死白 */
  background-blend-mode: multiply;
  border: 1px solid #ecdccb;
  box-shadow: 0 6px 16px rgba(150, 110, 80, 0.08);
}
.zoom__main .card__ph {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.zoom__lens {
  position: absolute;
  border: 1px solid rgba(193, 116, 79, 0.65);
  background: rgba(193, 116, 79, 0.22);
  box-shadow: inset 0 0 10px rgba(193, 116, 79, 0.3);
  border-radius: 2px;
  pointer-events: none;
}
.zoom__result {
  position: absolute;
  top: 0;
  /* left 由 previewStyle 注入：紧贴舞台右侧，随舞台宽度变化 */
  width: 300px;
  height: 300px;
  z-index: 30;
  pointer-events: none;
  border-radius: var(--mall-radius-lg);
  border: 1px solid #ecdccb;
  background-color: var(--mall-stage);
  background-repeat: no-repeat;
  background-blend-mode: multiply; /* 与舞台同色、同混合，预览区不会有白色断层 */
  box-shadow: 0 12px 32px rgba(120, 80, 50, 0.28);
}

/* 左栏信息卡：补齐左栏高度，避免下方留白 */
.d-facts {
  list-style: none;
  margin: 0;
  padding: 8px 14px;
  background: var(--mall-card);
  border: 1px solid #f0e2d4;
  border-radius: var(--mall-radius-lg);
}
.d-facts li {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 5px 0;
  font-size: 12px;
  line-height: 18px;
}
.d-facts li + li {
  border-top: 1px dashed #f2e6da;
}
.d-facts li > span {
  flex-shrink: 0;
  width: 30px;
  color: var(--mall-text-light);
}
.d-facts li > b {
  min-width: 0;
  font-weight: 500;
  color: var(--mall-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.d-facts li > b.d-facts__pick {
  color: var(--mall-primary);
}

/* 段落小标题（替代体积较大的 el-divider） */
.sec-label {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin: 14px 0 8px;
  padding-left: 8px;
  border-left: 3px solid var(--mall-primary);
  font-size: 13px;
  font-weight: 600;
  line-height: 16px;
  color: var(--mall-text);
}
.sec-label i {
  font-style: normal;
  font-weight: 400;
  font-size: 11px;
  color: var(--mall-text-light);
}
.detail-name {
  font-family: var(--mall-font-serif);
  font-size: 17px;
  color: var(--mall-text);
  margin: 0 0 8px;
  line-height: 1.4;
}
.detail-price-box {
  background: #f8f1ea;
  border-radius: var(--mall-radius);
  padding: 12px 14px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.detail-price-label {
  font-size: 13px;
  color: var(--mall-text-light);
}
.detail-price-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--mall-price);
}
.detail-price-num i {
  font-style: normal;
  font-size: 13px;
  font-weight: 400;
}
.detail-stock {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-left: auto;
}
.sku-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
  max-height: 212px; /* 限高：规格再多也不把右栏撑长，留白可控 */
  overflow-y: auto;
  padding-right: 4px;
}
.sku-list::-webkit-scrollbar {
  width: 4px;
}
.sku-list::-webkit-scrollbar-thumb {
  background: #e6d5c5;
  border-radius: 2px;
}
.sku-item {
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius);
  padding: 7px 10px;
  cursor: pointer;
  background: #fff;
  transition: border-color 0.15s, background 0.15s;
}
.sku-item__main {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.sku-item:hover {
  border-color: var(--mall-primary);
}
.sku-item.active {
  border-color: var(--mall-primary);
  background: var(--mall-primary-soft);
}
.sku-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: #fbf7f3;
}
.sku-item.disabled .sku-spec {
  text-decoration: line-through;
}
.sku-spec {
  min-width: 0;
  font-size: 12px;
  color: var(--mall-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sku-price {
  flex-shrink: 0;
  font-size: 14px;
  color: var(--mall-price);
  font-weight: 600;
}
.sku-stock {
  margin-top: 1px;
  font-size: 11px;
  color: var(--mall-text-light);
}
.sku-stock--empty {
  color: #c8695a;
}
.buy-qty {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 14px 0;
}
.qty-label {
  font-size: 14px;
  color: var(--mall-text);
}
.buy-actions {
  display: flex;
  gap: 12px;
}
.buy-actions .el-button {
  flex: 1;
}

/* ---------- 用户评价 ---------- */
.reviews {
  min-height: 40px;
}
.rev-stats {
  display: flex;
  align-items: baseline;
  gap: 14px;
  padding: 10px 12px;
  margin-bottom: 12px;
  background: #f8f1ea;
  border-radius: var(--mall-radius);
}
.rev-avg {
  font-size: 13px;
  color: var(--mall-text-light);
}
.rev-avg b {
  font-size: 26px;
  color: var(--mall-price);
  font-weight: 700;
  margin-right: 2px;
}
.rev-total {
  font-size: 13px;
  color: var(--mall-text-light);
}
.rev-item {
  padding: 12px 0;
  border-bottom: 1px dashed var(--mall-border);
}
.rev-item:last-child {
  border-bottom: none;
}
.rev-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.rev-user {
  font-size: 13px;
  color: var(--mall-text);
  font-weight: 600;
}
.rev-time {
  margin-left: auto;
  font-size: 12px;
  color: var(--mall-text-light);
}
.rev-content {
  font-size: 13px;
  color: var(--mall-text-regular);
  line-height: 1.6;
  margin-bottom: 8px;
}
.rev-pics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.rev-pic {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: var(--mall-radius-sm);
  border: 1px solid var(--mall-border);
  cursor: pointer;
}
.rev-reply {
  font-size: 12px;
  color: var(--mall-primary);
  background: var(--mall-primary-soft);
  border-radius: var(--mall-radius);
  padding: 6px 10px;
  line-height: 1.5;
}

/* ---------- 相关推荐 ---------- */
.similar {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  min-height: 40px;
}
.similar__card {
  background: var(--mall-card);
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius);
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.similar__card:hover {
  border-color: var(--mall-primary);
  box-shadow: var(--mall-shadow-hover);
}
.similar__pic {
  width: 100%;
  aspect-ratio: 1 / 1;
  background: linear-gradient(160deg, #fdf8f2 0%, #f4e9dd 100%);
  overflow: hidden;
}
.similar__pic img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.similar__name {
  font-size: 13px;
  line-height: 1.4;
  color: var(--mall-text);
  margin: 8px 8px 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  height: 36px;
}
.similar__price-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
  margin: 0 8px 8px;
}
.similar__price {
  color: var(--mall-price);
  font-weight: 700;
  font-size: 16px;
  line-height: 1;
}
.similar__price i {
  font-style: normal;
  font-size: 11px;
  font-weight: 400;
  margin-right: 1px;
}
.similar__sale {
  font-size: 11px;
  color: var(--mall-text-light);
  flex-shrink: 0;
}

/* 搜索关键词高亮 */
:deep(mark) {
  background: transparent;
  color: var(--mall-primary);
  font-weight: 600;
}
</style>
