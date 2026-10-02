import request from '@/utils/request'

export interface CollectItem {
  id: number
  memberId?: number
  productId: number
  productName?: string
  productPic?: string
  productPrice?: number | string
  createTime?: string
}

// 收藏商品
export function addCollect(productId: number) {
  return request<null>({
    url: '/member/collect/add',
    method: 'post',
    params: { productId },
  })
}

// 取消收藏（按 会员+商品 删除）
export function removeCollect(productId: number) {
  return request<null>({
    url: '/member/collect/delete',
    method: 'post',
    params: { productId },
  })
}

// 我的收藏列表（按收藏时间倒序）
export function listCollects() {
  return request<CollectItem[]>({
    url: '/member/collect/list',
    method: 'get',
  })
}

// 是否已收藏某商品
export function isCollected(productId: number) {
  return request<boolean>({
    url: '/member/collect/isCollected',
    method: 'get',
    params: { productId },
  })
}
