/** 商品实体：字段严格对齐后端 GET /product/list 返回的 JSON */
export interface Product {
  id: number
  productSn: string // 后端生成的唯一货号
  name: string
  subTitle?: string
  pic?: string
  brandId: number // 关联 brand.id
  categoryId: number // 关联 category.id
  sale: number
  status: number // 1 上架 / 0 下架
  createTime: string // LocalDateTime 序列化为 ISO 字符串
  updateTime: string
}

/** 新增/修改商品的入参，对应后端 ProductParam（前端可传字段白名单） */
export interface ProductParam {
  name: string
  subTitle?: string
  pic?: string
  brandId: number
  categoryId: number
  status?: number
}
