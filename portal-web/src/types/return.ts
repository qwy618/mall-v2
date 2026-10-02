// 售后退货类型：对齐后端 OrderReturnApply 实体。
//
// 重要：C 端 `/return/detail` 返回的是实体本身，`proofPics` 与 `returnItems`
// 是 **JSON 字符串**（不是已解析数组），前端拿到后要 JSON.parse 再渲染。
// 这里 ReturnApplyEntity 保留原始字符串字段；视图层解析后转 ReturnApplyView。

/** 退货明细行（内联在 returnItems JSON 中，对应后端 ReturnItemDTO） */
export interface ReturnItemDTO {
  orderItemId?: number
  skuId?: number
  productId?: number
  productName?: string
  productPic?: string
  quantity?: number // 本次退货数量
  realAmount?: number // 该行退款金额（已按实付分摊，债务 7 落库）
}

/** 后端实体（C 端 detail/list 返回的原始结构，proofPics/returnItems 为 JSON 字符串） */
export interface ReturnApplyEntity {
  id?: number
  orderId?: number
  orderSn?: string
  memberId?: number
  returnAmount?: number
  reason?: string
  description?: string
  proofPics?: string // JSON 字符串：["url",...]
  returnItems?: string // JSON 字符串：ReturnItemDTO[]
  status?: number // 0待审核 1待退货(已同意) 2已拒绝 3已收货 4已完成 5已关闭
  handleNote?: string
  handleMan?: string
  companyAddress?: string // 退货收货地址（管理端同意后回传）
  returnTrackingNo?: string // 会员回填的退货物流单号
  createTime?: string
  updateTime?: string
}

/** 前端解析后的视图模型（proofPics/returnItems 已解析为数组） */
export interface ReturnApplyView {
  id?: number
  orderId?: number
  orderSn?: string
  memberId?: number
  returnAmount?: number
  reason?: string
  description?: string
  proofPics?: string[]
  items?: ReturnItemDTO[]
  status?: number
  handleNote?: string
  handleMan?: string
  companyAddress?: string
  returnTrackingNo?: string
  createTime?: string
}

/** 申请退货入参：对应后端 ReturnApplyParam */
export interface ApplyItemParam {
  orderItemId: number
  quantity: number
}

export interface ReturnApplyParam {
  orderId: number
  items: ApplyItemParam[]
  reason: string
  description?: string
  proofPics?: string[]
}

/** 退货状态枚举：0待审核 1待退货 2已拒绝 3已收货 4已完成 5已关闭 */
export const RETURN_STATUS_TEXT: Record<number, string> = {
  0: '待审核',
  1: '待退货',
  2: '已拒绝',
  3: '已收货',
  4: '已完成',
  5: '已关闭',
}

/** 状态对应 el-tag 颜色类型 */
export const RETURN_STATUS_TAG: Record<number, 'warning' | 'primary' | 'danger' | 'success' | 'info'> = {
  0: 'warning',
  1: 'primary',
  2: 'danger',
  3: 'info',
  4: 'success',
  5: 'info',
}

/** 申请原因快捷选项 */
export const RETURN_REASONS = ['质量问题', '尺寸/颜色不符', '不喜欢/不想要了', '发错货/漏发', '其他']
