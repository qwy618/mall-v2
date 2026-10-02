// 商品评价管理端类型（对齐 mall-admin /comment 接口）

export interface CommentListItem {
  id: number
  orderItemId: number
  orderId: number
  orderSn?: string
  productId?: number
  productName?: string
  productPic?: string
  memberId?: number
  nickname?: string
  star: number
  content?: string
  pics?: string | string[]
  anonymous?: number
  status: number // 0 待审核 1 通过 2 驳回
  replyContent?: string
  createTime?: string
  updateTime?: string
}

export interface CommentQuery {
  pageNum: number
  pageSize: number
  productId?: number
  status?: number
  keyword?: string
}

// 评价状态常量
export const COMMENT_STATUS_TEXT: Record<number, string> = {
  0: '待审核',
  1: '已通过',
  2: '已驳回',
}

export function commentPics(pics?: string | string[]): string[] {
  if (!pics) return []
  if (Array.isArray(pics)) return pics
  try {
    const arr = JSON.parse(pics)
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}
