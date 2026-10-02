<template>
  <div class="page">
    <div class="crumb">
      <span class="link" @click="router.push('/product')">商品</span>
      <span class="sep">/</span>
      <span>购物车</span>
    </div>
    <h2 class="page-title">购物车</h2>

    <div v-loading="loading" class="cart-box">
      <template v-if="cart.length">
        <div class="cart-head">
          <el-checkbox
            :model-value="isAllSelected"
            :indeterminate="isIndeterminate"
            @change="toggleAll"
          >全选</el-checkbox>
          <span class="head-col goods-col">商品</span>
          <span class="head-col price-col">单价</span>
          <span class="head-col qty-col">数量</span>
          <span class="head-col sub-col">小计</span>
          <span class="head-col op-col">操作</span>
        </div>

        <div v-for="c in cart" :key="c.cartItemId" class="cart-row" :class="{ offline: c.offline }">
          <el-checkbox
            :model-value="selectedIds.includes(c.cartItemId)"
            :disabled="c.offline"
            @change="(v: any) => toggle(c, v)"
          />
          <div class="goods-col goods">
            <PicBox
              class="g-img"
              :pic="c.pic"
              :name="c.productName"
              :ratio="1"
              :scale="1"
              ph-class="img-ph"
            />
            <div class="g-info">
              <div class="g-name">
                {{ c.productName }}
                <span v-if="c.offline" class="g-invalid">已失效</span>
              </div>
              <div v-if="c.skuCode" class="g-spec">{{ c.skuCode }}</div>
              <div v-if="!c.offline && (c.stock || 0) <= 0" class="g-out">已售罄</div>
              <div v-if="c.offline" class="g-out">商品已下架，不可结算</div>
            </div>
          </div>
          <div class="price-col price">￥{{ money(c.price) }}</div>
          <div class="qty-col">
            <el-input-number
              :model-value="c.quantity"
              :min="1"
              :max="c.offline ? 999 : ((c.stock || 1) > 0 ? (c.stock as number) : 99)"
              :disabled="c.offline"
              size="small"
              @change="(v: any) => onQtyChange(c, v)"
            />
          </div>
          <div class="sub-col sub">￥{{ money((c.price || 0) * c.quantity) }}</div>
          <div class="op-col">
            <el-button text type="danger" @click="removeItem(c)">删除</el-button>
          </div>
        </div>
      </template>

      <el-empty v-else description="购物车还是空的，去逛逛吧" />
    </div>

    <div v-if="cart.length" class="settle-bar">
      <el-checkbox
        :model-value="isAllSelected"
        :indeterminate="isIndeterminate"
        @change="toggleAll"
      >全选</el-checkbox>
      <el-button text type="danger" @click="removeSelected">删除选中</el-button>
      <el-button v-if="offlineCount > 0" text type="info" @click="cleanOffline">
        清理失效商品({{ offlineCount }})
      </el-button>
      <div class="settle-right">
        <span class="total-label">已选 {{ selectedCount }} 件，合计</span>
        <span class="total-num">￥{{ money(selectedTotal) }}</span>
        <el-button
          type="primary"
          size="large"
          :disabled="selectedIds.length === 0"
          :loading="settling"
          @click="goCheckout"
        >去结算</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listCart, updateCartQuantity, deleteCartItem, checkCartItem } from '@/apis/cart'
import type { CartItemVO } from '@/apis/cart'
import { useUserStore } from '@/stores/user'
import { useLoginGate } from '@/stores/loginGate'
import { getGuestCart, updateGuestCartQuantity, removeGuestCartItem } from '@/utils/guestCart'
import type { GuestCartItem } from '@/utils/guestCart'
import PicBox from '@/components/PicBox.vue'

const router = useRouter()
const userStore = useUserStore()
const cart = ref<CartItemVO[]>([])
const selectedIds = ref<number[]>([])
const loading = ref(false)
const settling = ref(false)

function money(n?: number) {
  return (Number(n) || 0).toFixed(2)
}

// 未登录：把本地暂存车映射成与会员购物车同构的视图对象，复用同一套渲染
function toGuestVO(g: GuestCartItem): CartItemVO {
  return {
    cartItemId: g.skuId, // 游客行用 skuId 作唯一键
    skuId: g.skuId,
    productId: g.productId,
    skuCode: g.skuCode,
    productName: g.name,
    pic: g.pic,
    spData: g.spData,
    price: g.price,
    stock: 99, // 游客无实时库存，给正常值避免误显示"已售罄"
    quantity: g.quantity,
    checked: 1,
    offline: false,
  }
}

async function loadCart() {
  loading.value = true
  try {
    // 未登录：直接读本地暂存车（不打扰、不弹窗）
    if (!userStore.token) {
      const list = getGuestCart().map(toGuestVO)
      cart.value = list
      selectedIds.value = list.map((c) => c.cartItemId)
      return
    }
    const list = await listCart()
    cart.value = list
    // 默认只选在线商品（失效商品不可结算）
    const onlineIds = list.filter((c) => !c.offline).map((c) => c.cartItemId)
    const ids = new Set(list.map((c) => c.cartItemId))
    selectedIds.value = selectedIds.value.filter((id) => ids.has(id) && onlineIds.includes(id))
    if (selectedIds.value.length === 0) {
      selectedIds.value = onlineIds
    }
  } finally {
    loading.value = false
  }
}

// 登录态变化（如在本页完成登录回来）时重载
watch(
  () => userStore.token,
  () => loadCart()
)

const selectedCount = computed(() => selectedIds.value.length)

const selectedTotal = computed(() =>
  cart.value
    .filter((c) => selectedIds.value.includes(c.cartItemId))
    .reduce((sum, c) => sum + (c.price || 0) * c.quantity, 0)
)

const isAllSelected = computed(
  () => cart.value.length > 0 && selectedIds.value.length === cart.value.length
)

const isIndeterminate = computed(
  () => selectedIds.value.length > 0 && selectedIds.value.length < cart.value.length
)

const offlineCount = computed(() => cart.value.filter((c) => c.offline).length)

async function toggle(item: CartItemVO, checked: boolean) {
  if (item.offline) return // 失效商品不可选
  const id = item.cartItemId
  if (checked) {
    if (!selectedIds.value.includes(id)) selectedIds.value = [...selectedIds.value, id]
  } else {
    selectedIds.value = selectedIds.value.filter((x) => x !== id)
  }
  if (!userStore.token) return // 游客：勾选只存本地
  try {
    await checkCartItem(id, checked ? 1 : 0)
  } catch {
    // 提示已由拦截器给出，状态以本地为准
  }
}

async function toggleAll(val: boolean) {
  if (val) {
    selectedIds.value = cart.value.filter((c) => !c.offline).map((c) => c.cartItemId)
  } else {
    selectedIds.value = []
  }
  if (!userStore.token) return
  // 同步后端勾选状态（仅在线商品）
  await Promise.all(
    cart.value
      .filter((c) => !c.offline)
      .map((c) => checkCartItem(c.cartItemId, val ? 1 : 0).catch(() => null))
  )
}

async function cleanOffline() {
  const offlineIds = cart.value.filter((c) => c.offline).map((c) => c.cartItemId)
  if (offlineIds.length === 0) return
  await Promise.all(offlineIds.map((id) => deleteCartItem(id).catch(() => null)))
  ElMessage.success('已清理失效商品')
  await loadCart()
}

async function onQtyChange(item: CartItemVO, val: number) {
  const qty = Number(val) || 1
  const prev = item.quantity
  item.quantity = qty // 本地先更新，避免闪
  if (!userStore.token) {
    updateGuestCartQuantity(item.skuId, qty)
    return
  }
  try {
    await updateCartQuantity(item.cartItemId, qty)
  } catch {
    item.quantity = prev // 失败回滚
    await loadCart()
  }
}

async function removeItem(item: CartItemVO) {
  if (!userStore.token) {
    removeGuestCartItem(item.skuId)
    ElMessage.success('已删除')
    selectedIds.value = selectedIds.value.filter((x) => x !== item.cartItemId)
    await loadCart()
    return
  }
  try {
    await deleteCartItem(item.cartItemId)
    ElMessage.success('已删除')
    selectedIds.value = selectedIds.value.filter((x) => x !== item.cartItemId)
    await loadCart()
  } catch {
    // 提示已给出
  }
}

async function removeSelected() {
  if (selectedIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedIds.value.length} 项？`, '提示', {
      type: 'warning',
    })
  } catch {
    return
  }
  if (!userStore.token) {
    // 游客：cartItemId 即 skuId
    selectedIds.value.forEach((id) => removeGuestCartItem(id))
  } else {
    await Promise.all(selectedIds.value.map((id) => deleteCartItem(id).catch(() => null)))
  }
  selectedIds.value = []
  await loadCart()
}

function goCheckout() {
  if (selectedIds.value.length === 0) return
  // 游客结算：引导登录（登录后暂存车自动并入，再回来结算）
  if (!userStore.token) {
    useLoginGate().require('/cart', '登录后即可结算，购物车里的商品会一起带过来')
    return
  }
  settling.value = true
  try {
    router.push({
      path: '/order/confirm',
      query: { cartItemIds: selectedIds.value.join(',') },
    })
  } finally {
    settling.value = false
  }
}

onMounted(loadCart)
</script>

<style scoped>
.page {
  padding: 20px 24px 80px;
  background: var(--mall-bg);
  min-height: calc(100vh - 60px);
}
.crumb {
  font-size: 13px;
  color: var(--mall-text-light);
  margin-bottom: 16px;
}
.crumb .link {
  cursor: pointer;
  color: var(--mall-primary);
}
.crumb .sep {
  margin: 0 6px;
}
.cart-box {
  background: var(--mall-card);
  border-radius: var(--mall-radius);
  padding: 8px 20px;
  box-shadow: var(--mall-shadow);
  min-height: 120px;
}
.cart-head {
  display: flex;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid var(--mall-border);
  font-size: 13px;
  color: var(--mall-text-light);
}
.cart-row {
  display: flex;
  align-items: center;
  padding: 16px 0;
  border-bottom: 1px dashed var(--mall-border);
}
.cart-row:last-child {
  border-bottom: none;
}
.goods-col {
  flex: 1;
  min-width: 0;
}
.price-col {
  width: 110px;
  text-align: center;
}
.qty-col {
  width: 140px;
  text-align: center;
}
.sub-col {
  width: 110px;
  text-align: center;
}
.op-col {
  width: 90px;
  text-align: center;
}
.head-col.goods-col {
  margin-left: 12px;
}
.goods {
  display: flex;
  align-items: center;
  gap: 12px;
}
.g-img {
  width: 60px;
  height: 60px;
  border-radius: var(--mall-radius-sm);
  background: var(--mall-primary-soft);
  overflow: hidden;
  flex: 0 0 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.g-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.img-ph {
  font-size: 24px;
  font-weight: 700;
  color: var(--mall-text-light);
}
.g-name {
  font-size: 14px;
  color: var(--mall-text);
  margin-bottom: 4px;
}
.g-invalid {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  font-size: 11px;
  line-height: 16px;
  color: #fff;
  background: #b0a99f;
  border-radius: 4px;
  vertical-align: middle;
}
.cart-row.offline {
  opacity: 0.55;
  filter: grayscale(0.6);
}
.cart-row.offline .g-name {
  color: var(--mall-text-light);
}
.g-spec {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-bottom: 2px;
}
.g-out {
  font-size: 12px;
  color: var(--mall-price);
}
.price {
  font-size: 14px;
  color: var(--mall-price);
}
.sub {
  font-size: 15px;
  font-weight: 600;
  color: var(--mall-price);
}
.settle-bar {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 16px;
  padding: 14px 20px;
  background: var(--mall-card);
  border-radius: var(--mall-radius);
  box-shadow: var(--mall-shadow-hover);
}
.settle-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
}
.total-label {
  font-size: 14px;
  color: var(--mall-text-light);
}
.total-num {
  font-size: 26px;
  font-weight: 700;
  color: var(--mall-price);
}
</style>
