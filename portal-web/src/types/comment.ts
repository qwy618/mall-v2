// 商品评价相关类型（对齐 mall-portal 评价接口）
// 注意：后端 pics 存 JSON 字符串，VO 可能返回数组或字符串，前端统一兼容解析。

export interface CommentSubmitParam {
  orderItemId: number
  star: number
  content?: string
  pics?: string[]
  anonymous?: boolean
}

export interface ProductCommentVO {
  id: number
  orderItemId: number
  productId: number
  star: number
  content?: string
  pics?: string | string[]
  anonymous?: number
  nickname?: string
  icon?: string
  createTime?: string
  replyContent?: string
  replyTime?: string
}

export interface CommentStats {
  avgStar: number
  total: number
  fiveStar: number
  fourStar: number
  threeStar: number
  twoStar: number
  oneStar: number
}

export interface MyComment extends ProductCommentVO {
  status?: number
  productPic?: string
  productName?: string
}

// 兼容后端 pics：字符串(JSON) 或 数组，统一转为字符串数组
export function toPics(pics?: string | string[]): string[] {
  if (!pics) return []
  if (Array.isArray(pics)) return pics
  try {
    const arr = JSON.parse(pics)
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}
