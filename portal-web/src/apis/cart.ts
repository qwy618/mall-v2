import request from '@/utils/request'

// 购物车项视图（对齐后端 CartItemVO）
export interface CartItemVO {
  cartItemId: number
  skuId: number
  productId?: number
  skuCode?: string
  productName?: string
  pic?: string
  spData?: string // 规格JSON（快照）
  price?: number
  stock?: number
  quantity: number
  checked: number // 1选中 0未选
  offline?: boolean // true=商品已下架/失效，灰显且不可结算
}

// 合并入参（对齐后端 CartMergeParam）
export interface CartMergeItem {
  skuId: number
  quantity: number
}

// 购物车列表
export function listCart() {
  return request<CartItemVO[]>({
    url: '/cart/list',
    method: 'get',
  })
}

// 加入购物车
export function addCart(skuId: number, quantity = 1) {
  return request<null>({
    url: '/cart/add',
    method: 'post',
    params: { skuId, quantity },
  })
}

// 修改购物车项数量
export function updateCartQuantity(cartItemId: number, quantity: number) {
  return request<null>({
    url: '/cart/update',
    method: 'post',
    params: { cartItemId, quantity },
  })
}

// 删除购物车项
export function deleteCartItem(cartItemId: number) {
  return request<null>({
    url: '/cart/delete',
    method: 'delete',
    params: { cartItemId },
  })
}

// 勾选 / 取消勾选（同步后端 checked 状态）
export function checkCartItem(cartItemId: number, checked: number) {
  return request<null>({
    url: '/cart/check',
    method: 'post',
    params: { cartItemId, checked },
  })
}

// 未登录购物车合并：登录成功后把 localStorage 暂存车批量合并进会员购物车
export function mergeGuestCart(items: CartMergeItem[]) {
  return request<null>({
    url: '/cart/merge',
    method: 'post',
    data: items,
  })
}
