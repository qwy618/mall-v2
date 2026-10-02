/** SKU 实体：字段严格对齐后端 GET /sku/list 返回的 JSON */
export interface Sku {
  id: number
  productId: number
  skuCode: string // 后端生成的唯一 SKU 编码
  spData?: string // 规格数据 JSON，可空
  price: number // 后端 decimal(10,2) 序列化为 number
  stock: number
  lockStock: number
  pic?: string
  sale: number
  createTime: string
  updateTime: string
}

/** 新增/修改 SKU 的入参，对应后端 SkuParam（前端可传字段白名单） */
export interface SkuParam {
  productId: number
  spData?: string
  price: number
  stock?: number
  lockStock?: number
  pic?: string
  sale?: number
}
