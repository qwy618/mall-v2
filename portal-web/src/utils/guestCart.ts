// 未登录购物车（暂存车）：登录前加购的商品先落 localStorage，登录后合并进会员购物车。
// 与会员购物车（后端 cart_item）解耦，仅用于"未登录 → 登录"这一过渡态。
// 存商品快照（名称/图/规格/价格）是为了让"未登录也能看购物车"页无需额外接口即可渲染。
const KEY = 'guestCart'

export interface GuestCartItem {
  skuId: number
  quantity: number
  productId?: number
  name?: string
  pic?: string
  spData?: string
  price?: number
  skuCode?: string
}

export function getGuestCart(): GuestCartItem[] {
  try {
    const raw = localStorage.getItem(KEY)
    const arr = raw ? JSON.parse(raw) : []
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

function save(list: GuestCartItem[]) {
  localStorage.setItem(KEY, JSON.stringify(list))
}

// 加购：同 sku 累加数量；带快照时以最新快照覆盖（防商品改名/调价后显示陈旧）
export function addGuestCart(
  skuId: number,
  quantity: number,
  snapshot?: Omit<GuestCartItem, 'skuId' | 'quantity'>
) {
  const list = getGuestCart()
  const found = list.find((i) => i.skuId === skuId)
  if (found) {
    found.quantity += quantity
    if (snapshot) Object.assign(found, snapshot)
  } else {
    list.push({ skuId, quantity, ...(snapshot || {}) })
  }
  save(list)
}

export function updateGuestCartQuantity(skuId: number, quantity: number) {
  const list = getGuestCart()
  const found = list.find((i) => i.skuId === skuId)
  if (found) {
    found.quantity = quantity
    save(list)
  }
}

export function removeGuestCartItem(skuId: number) {
  save(getGuestCart().filter((i) => i.skuId !== skuId))
}

export function clearGuestCart() {
  localStorage.removeItem(KEY)
}

export function guestCartCount(): number {
  return getGuestCart().reduce((sum, i) => sum + (i.quantity || 0), 0)
}
