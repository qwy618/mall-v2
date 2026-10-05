<template>
  <div class="page">
    <div class="crumb">
      <span class="link" @click="router.push('/product')">商品</span>
      <span class="sep">/</span>
      <span>确认订单</span>
    </div>
    <h2 class="page-title">确认订单</h2>

    <div class="box">
      <div class="box-title">收货地址</div>
      <div class="addr-grid">
        <div
          v-for="a in addresses"
          :key="a.id"
          class="addr-card"
          :class="{ active: selectedAddrId === a.id }"
          @click="selectedAddrId = a.id!"
        >
          <div class="addr-top">
            <span class="addr-name">{{ a.receiverName }}</span>
            <span class="addr-phone">{{ a.phone }}</span>
            <span v-if="a.defaultStatus === 1" class="tag-default">默认</span>
          </div>
          <div class="addr-detail">
            {{ a.province }}{{ a.city }}{{ a.district }} {{ a.detailAddress }}
          </div>
        </div>
        <div class="addr-card addr-add" @click="showAddrDialog = true">
          <div class="plus">+</div>
          <div>新增地址</div>
        </div>
      </div>
      <el-empty v-if="!addrLoading && addresses.length === 0" description="还没有收货地址，先添加一个吧" />
    </div>

    <div class="box">
      <div class="box-title">商品清单</div>
      <div class="goods-list">
        <div v-for="(it, idx) in items" :key="idx" class="goods-row">
          <PicBox
            class="g-img"
            :pic="it.pic"
            :name="it.name"
            :ratio="1"
            :scale="1"
            ph-class="img-ph"
          />
          <div class="g-info">
            <div class="g-name">{{ it.name }}</div>
            <div v-if="it.specText" class="g-spec">{{ it.specText }}</div>
          </div>
          <div class="g-price">￥{{ money(it.price) }}</div>
          <div class="g-qty">x{{ it.quantity }}</div>
          <div class="g-sub">￥{{ money(it.price * it.quantity) }}</div>
        </div>
      </div>
      <div v-if="items.length === 0" class="empty-tip">没有可结算的商品</div>
    </div>

    <div class="box">
      <div class="box-title">优惠券</div>
      <div class="coupon-list">
        <div
          class="coupon-card"
          :class="{ active: selectedCouponId === null }"
          @click="selectedCouponId = null"
        >
          <div class="coupon-name">不使用优惠券</div>
          <div class="coupon-desc">按原价结算</div>
        </div>
        <div
          v-for="c in couponEstimates"
          :key="c.coupon.id"
          class="coupon-card"
          :class="{ active: selectedCouponId === c.coupon.id, disabled: !c.usable }"
          @click="c.usable && (selectedCouponId = c.coupon.id)"
        >
          <div class="coupon-amt">-￥{{ money(couponDiscount(c)) }}</div>
          <div class="coupon-name">{{ c.coupon.name }}</div>
          <div class="coupon-desc">{{ c.usable ? couponDesc(c.coupon) : (c.reason || '当前订单不可用') }}</div>
        </div>
      </div>
      <el-empty
        v-if="!couponLoading && couponEstimates.length === 0"
        description="暂无可用优惠券"
      />
    </div>

    <!-- 积分抵扣（债务18）：100 积分 = 1 元 -->
    <div v-if="maxUsablePoints > 0" class="box">
      <div class="box-title">积分抵扣</div>
      <div class="point-row">
        <div class="point-info">
          <div class="point-balance">
            可用积分 <b>{{ availablePoints }}</b>，本单最多可用 <b>{{ maxUsablePoints }}</b>
          </div>
          <div class="point-tip">
            100 积分 = 1 元<span v-if="levelName">
              · {{ levelName }}
              {{ discountRate >= 100 ? '暂无折扣' : discountRate / 10 + ' 折' }}</span>
          </div>
        </div>
        <el-switch v-model="usePoint" active-text="使用积分" />
      </div>
      <div v-if="usePoint && integrationAmount > 0" class="point-result">
        已使用 {{ useIntegration }} 积分，抵扣 ￥{{ money(integrationAmount) }}
      </div>
    </div>

    <div class="box settle">
      <div class="settle-row">
        <span>商品合计</span>
        <span class="num">￥{{ money(totalAmount) }}</span>
      </div>
      <div class="settle-row">
        <span>运费</span>
        <span class="num">￥{{ money(freightAmount) }}</span>
      </div>
      <div class="settle-row" v-if="promotionAmount > 0">
        <span>会员折扣（{{ levelName }}）</span>
        <span class="num discount">-￥{{ money(promotionAmount) }}</span>
      </div>
      <div class="settle-row" v-if="couponAmount > 0">
        <span>优惠券抵扣</span>
        <span class="num discount">-￥{{ money(couponAmount) }}</span>
      </div>
      <div class="settle-row" v-if="integrationAmount > 0">
        <span>积分抵扣（{{ useIntegration }} 积分）</span>
        <span class="num discount">-￥{{ money(integrationAmount) }}</span>
      </div>
      <div class="settle-foot">
        <span class="pay-label">应付</span>
        <span class="pay-num">￥{{ money(payAmount) }}</span>
        <el-button
          type="primary"
          size="large"
          :disabled="!canSubmit || previewLoading"
          :loading="submitting"
          @click="submit"
        >提交订单</el-button>
      </div>
    </div>

    <!-- 新增地址弹窗 -->
    <el-dialog v-model="showAddrDialog" title="新增收货地址" width="460px">
      <el-form :model="addrForm" label-width="80px">
        <el-form-item label="收货人">
          <el-input v-model="addrForm.receiverName" placeholder="收货人姓名" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="addrForm.phone" placeholder="11 位手机号" maxlength="11" />
        </el-form-item>
        <el-form-item label="省">
          <el-input v-model="addrForm.province" placeholder="省 / 直辖市" />
        </el-form-item>
        <el-form-item label="市">
          <el-input v-model="addrForm.city" placeholder="市" />
        </el-form-item>
        <el-form-item label="区/县">
          <el-input v-model="addrForm.district" placeholder="区 / 县" />
        </el-form-item>
        <el-form-item label="详细地址">
          <el-input v-model="addrForm.detailAddress" type="textarea" :rows="2" placeholder="街道、门牌号等" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="addrForm.isDefault" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddrDialog = false">取消</el-button>
        <el-button type="primary" :loading="addrSaving" @click="saveAddress">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getProduct } from '@/apis/product'
import { listCart } from '@/apis/cart'
import { listAddresses, addAddress } from '@/apis/address'
import { createOrder, generateOrderToken, previewOrder } from '@/apis/order'
import { estimateCoupons } from '@/apis/coupon'
import { getMemberLevel } from '@/apis/member'
import { formatSpec } from '@/utils/spec'
import type { Address, OrderPreviewVO } from '@/types/order'
import type { CouponEstimate } from '@/types/coupon'
import type { MemberLevelVO } from '@/types/member'
import PicBox from '@/components/PicBox.vue'

const route = useRoute()
const router = useRouter()

interface ConfirmItem {
  skuId: number
  quantity: number
  cartItemId: number | null
  name: string
  pic?: string
  price: number
  specText?: string
}

const items = ref<ConfirmItem[]>([])
const loading = ref(false)

const addresses = ref<Address[]>([])
const selectedAddrId = ref<number | null>(null)
const addrLoading = ref(false)

// 优惠券（后端预估的可用券列表）
const couponEstimates = ref<CouponEstimate[]>([])
const selectedCouponId = ref<number | null>(null) // null = 不使用
const couponLoading = ref(false)

// ===== 债务18：会员等级（折扣率 + 积分余额）=====
const levelInfo = ref<MemberLevelVO | null>(null)
const usePoint = ref(false) // 是否使用积分抵扣（使用即用满本单可抵额度）

const submitting = ref(false)
const orderToken = ref('') // 下单幂等令牌（债务23）：进页面取号，提交时带回

// 取号：一次性令牌。同一令牌重复提交不会重复下单（后端 Redis Lua 原子认领）
async function fetchOrderToken() {
  try {
    orderToken.value = await generateOrderToken()
  } catch {
    orderToken.value = ''
  }
}

const showAddrDialog = ref(false)
const addrSaving = ref(false)
const addrForm = reactive({
  receiverName: '',
  phone: '',
  province: '',
  city: '',
  district: '',
  detailAddress: '',
  isDefault: false,
})

function money(n?: number) {
  return (Number(n) || 0).toFixed(2)
}

const canSubmit = computed(
  () => items.value.length > 0 && selectedAddrId.value != null && !submitting.value
)

// 单张券的预计优惠（直接取后端预估值，后端 couponAmount 为权威值）
function couponDiscount(c: CouponEstimate) {
  return c.discount
}

function couponDesc(coupon: { discount?: number; amount?: number; minPoint?: number }) {
  if (coupon.discount && coupon.discount > 0 && coupon.discount < 1) {
    return `打 ${Math.round(coupon.discount * 100) / 10} 折`
  }
  if (coupon.amount && coupon.amount > 0) {
    const min = Number(coupon.minPoint) || 0
    return min > 0 ? `满 ${money(min)} 减 ${money(coupon.amount)}` : `立减 ${money(coupon.amount)}`
  }
  return '优惠券'
}

// ===== M1.4 金额同源：确认页不再本地算钱 =====
// 所有金额一律取自后端 `POST /order/preview`——它与真正下单 /order/create 共用同一段
// 计算代码（OrderServiceImpl.computeAmounts），因此卡片金额与最终扣款逐分一致。
const preview = ref<OrderPreviewVO | null>(null)
const previewLoading = ref(false)

// 商品合计 / 运费 / 会员折扣 / 优惠券：均为后端权威值
const totalAmount = computed(() => Number(preview.value?.totalAmount) || 0)
const freightAmount = computed(() => Number(preview.value?.freightAmount) || 0)
const promotionAmount = computed(() => Number(preview.value?.promotionAmount) || 0)
const couponAmount = computed(() => Number(preview.value?.couponAmount) || 0)

const availablePoints = computed(() => levelInfo.value?.integration ?? 0)
const levelName = computed(() => preview.value?.levelName ?? levelInfo.value?.levelName ?? '')
const discountRate = computed(
  () => preview.value?.discountRate ?? levelInfo.value?.discountRate ?? 100
)

// 本单最多可用积分：后端按「账户余额 + 券后应付」双重封顶后的结果
const maxUsablePoints = computed(() => Number(preview.value?.useIntegration) || 0)

// 实际使用积分数（开关关闭时为 0）
const useIntegration = computed(() => (usePoint.value ? maxUsablePoints.value : 0))

// 积分抵扣金额（开关关闭时为 0）。preview 返回的是「用满积分」场景
const integrationAmount = computed(() =>
  usePoint.value ? Number(preview.value?.integrationAmount) || 0 : 0
)

// 应付：preview.payAmount 已扣满积分；未使用积分时把积分抵扣加回
const payAmount = computed(() => {
  const full = Number(preview.value?.payAmount) || 0
  const integ = Number(preview.value?.integrationAmount) || 0
  return Math.max(0, full + (usePoint.value ? 0 : integ))
})

// 订单试算：不扣库存、不落库、不消耗令牌，可安全反复调用
async function fetchPreview() {
  if (items.value.length === 0) {
    preview.value = null
    return
  }
  previewLoading.value = true
  try {
    preview.value = await previewOrder({
      addressId: selectedAddrId.value,
      couponId: selectedCouponId.value,
      items: items.value.map((it) => ({
        skuId: it.skuId,
        quantity: it.quantity,
        cartItemId: it.cartItemId,
      })),
      // 传「账户全部积分」：后端按余额与券后应付双重封顶，返回本单最多可用积分数；
      // 积分开关只决定是否把这份抵扣计入应付，无需重新试算
      useIntegration: availablePoints.value,
    })
  } catch {
    preview.value = null
  } finally {
    previewLoading.value = false
  }
}

// 券 / 地址变化都会影响试算结果，重新拉取（积分开关是纯展示，不触发）
watch([selectedCouponId, selectedAddrId], () => {
  fetchPreview()
})

async function fetchLevel() {
  try {
    levelInfo.value = await getMemberLevel()
  } catch {
    levelInfo.value = null
  }
}

// 入口一：立即购买（productId + skuId + quantity）
async function loadImmediateBuy() {
  const productId = Number(route.query.productId)
  const skuId = Number(route.query.skuId)
  const quantity = Number(route.query.quantity) || 1
  if (!productId || !skuId) return
  const data = await getProduct(productId)
  const sku = data.skus.find((s) => s.id === skuId)
  if (!sku) throw new Error('SKU 不存在')
  items.value = [
    {
      skuId,
      quantity,
      cartItemId: null,
      name: data.product.name,
      pic: data.product.pic,
      price: Number(sku.price) || 0,
      specText: formatSpec(sku.spData),
    },
  ]
}

// 入口二：购物车结算（cartItemIds 逗号分隔）
async function loadCartCheckout() {
  const raw = (route.query.cartItemIds as string) || ''
  if (!raw) return
  const ids = raw.split(',').map((x) => Number(x.trim())).filter(Boolean)
  const cart = await listCart()
  items.value = cart
    .filter((c) => ids.includes(c.cartItemId))
    .map((c) => ({
      skuId: c.skuId,
      quantity: c.quantity,
      cartItemId: c.cartItemId,
      name: c.productName || '',
      pic: c.pic,
      price: Number(c.price) || 0,
    }))
}

async function fetchAddresses() {
  addrLoading.value = true
  try {
    const list = await listAddresses()
    addresses.value = list
    const def = list.find((a) => a.defaultStatus === 1)
    selectedAddrId.value = def ? def.id! : list.length ? list[0].id! : null
  } finally {
    addrLoading.value = false
  }
}

async function fetchEstimate() {
  couponLoading.value = true
  try {
    // 把当前订单商品（skuId+quantity）发给后端，由后端用真实商品数据
    // 计算每张券的适用范围(couponBase)、门槛与优惠——前端不再本地算
    const orderItems = items.value.map((it) => ({ skuId: it.skuId, quantity: it.quantity }))
    couponEstimates.value = await estimateCoupons(orderItems)
  } catch {
    couponEstimates.value = []
  } finally {
    couponLoading.value = false
  }
}

async function saveAddress() {
  if (!addrForm.receiverName || !addrForm.phone || !addrForm.detailAddress) {
    ElMessage.warning('请填写收货人、手机号和详细地址')
    return
  }
  addrSaving.value = true
  try {
    const payload: Address = {
      receiverName: addrForm.receiverName,
      phone: addrForm.phone,
      province: addrForm.province,
      city: addrForm.city,
      district: addrForm.district,
      detailAddress: addrForm.detailAddress,
      defaultStatus: addrForm.isDefault ? 1 : 0,
    }
    await addAddress(payload)
    ElMessage.success('地址已保存')
    showAddrDialog.value = false
    await fetchAddresses()
  } finally {
    addrSaving.value = false
  }
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    const orderId = await createOrder({
      addressId: selectedAddrId.value!,
      items: items.value.map((it) => ({
        skuId: it.skuId,
        quantity: it.quantity,
        cartItemId: it.cartItemId,
      })),
      couponId: selectedCouponId.value,
      submitToken: orderToken.value,
      useIntegration: useIntegration.value, // 债务18：0/未使用则后端忽略
    })
    ElMessage.success('下单成功')
    router.replace({ path: '/order/detail', query: { orderId } })
  } catch (e) {
    // 错误已由响应拦截器提示；令牌失效（页面停留过久）则重新取号，便于用户直接重试
    const msg = (e as Error)?.message || ''
    if (msg.includes('令牌')) await fetchOrderToken()
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await fetchOrderToken()
    await fetchAddresses()
    await fetchLevel()
    if (route.query.productId) {
      await loadImmediateBuy()
    } else if (route.query.cartItemIds) {
      await loadCartCheckout()
    }
    await fetchEstimate()
    await fetchPreview()
    if (items.value.length === 0) {
      ElMessage.warning('没有可结算的商品')
    }
  } catch {
    // 错误提示
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page {
  padding: 20px 24px 40px;
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
.box {
  background: var(--mall-card);
  border-radius: var(--mall-radius);
  padding: 18px 20px;
  box-shadow: var(--mall-shadow);
  margin-bottom: 16px;
}
.box-title {
  font-size: 15px;
  font-weight: 700;
  font-family: var(--mall-font-serif);
  color: var(--mall-text);
  margin-bottom: 14px;
}
.addr-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}
.addr-card {
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-sm);
  padding: 14px;
  cursor: pointer;
  background: var(--mall-card);
  transition: all 0.2s;
}
.addr-card.active {
  border-color: var(--mall-primary);
  box-shadow: 0 0 0 2px rgba(192, 116, 79, 0.15);
}
.addr-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.addr-name {
  font-weight: 600;
  color: var(--mall-text);
}
.addr-phone {
  font-size: 13px;
  color: var(--mall-text-light);
}
.addr-detail {
  font-size: 13px;
  color: var(--mall-text);
  line-height: 1.5;
}
.addr-add {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--mall-text-light);
  border-style: dashed;
}
.addr-add .plus {
  font-size: 28px;
  line-height: 1;
  margin-bottom: 6px;
}
.goods-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.goods-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 0;
  border-bottom: 1px dashed var(--mall-border);
}
.goods-row:last-child {
  border-bottom: none;
}
.g-img {
  width: 64px;
  height: 64px;
  border-radius: var(--mall-radius-sm);
  background: var(--mall-primary-soft);
  overflow: hidden;
  flex: 0 0 64px;
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
  font-size: 26px;
  font-weight: 700;
  color: var(--mall-text-light);
}
.g-info {
  flex: 1;
  min-width: 0;
}
.g-name {
  font-size: 14px;
  color: var(--mall-text);
  margin-bottom: 4px;
}
.g-spec {
  font-size: 12px;
  color: var(--mall-text-light);
}
.g-price,
.g-sub {
  font-size: 14px;
  color: var(--mall-price);
  width: 90px;
  text-align: right;
}
.g-qty {
  font-size: 14px;
  color: var(--mall-text-light);
  width: 50px;
  text-align: center;
}
.empty-tip {
  color: var(--mall-text-light);
  font-size: 14px;
  text-align: center;
  padding: 20px 0;
}
.settle-foot {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  margin-top: 12px;
}
.pay-label {
  font-size: 14px;
  color: var(--mall-text-light);
}
.pay-num {
  font-size: 26px;
  font-weight: 700;
  color: var(--mall-price);
}
.settle-row {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: var(--mall-text);
  padding: 6px 0;
}
.settle-row .num {
  color: var(--mall-price);
}
.settle-row .num.discount {
  color: var(--mall-primary);
}
.coupon-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.coupon-card {
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-sm);
  padding: 12px 14px;
  cursor: pointer;
  background: var(--mall-card);
  transition: all 0.2s;
}
.coupon-card.active {
  border-color: var(--mall-primary);
  box-shadow: 0 0 0 2px rgba(192, 116, 79, 0.15);
}
.coupon-card.disabled {
  cursor: not-allowed;
  opacity: 0.55;
  background: var(--mall-bg);
}
.coupon-amt {
  font-size: 20px;
  font-weight: 700;
  color: var(--mall-primary);
  margin-bottom: 4px;
}
.coupon-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--mall-text);
  margin-bottom: 2px;
}
.coupon-desc {
  font-size: 12px;
  color: var(--mall-text-light);
}

/* 积分抵扣（债务18） */
.point-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.point-balance {
  font-size: 14px;
  color: var(--mall-text);
}
.point-balance b {
  color: var(--mall-primary);
  font-variant-numeric: tabular-nums;
}
.point-tip {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-top: 4px;
}
.point-result {
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: var(--mall-radius-sm);
  background: var(--mall-primary-soft);
  color: var(--mall-primary);
  font-size: 13px;
}
</style>
