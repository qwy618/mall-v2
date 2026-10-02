// 与后端 CommonPage 对齐
export interface PageResult<T> {
  pageNum: number
  pageSize: number
  totalPage: number
  total: number
  list: T[]
}

export interface Product {
  id: number
  name: string
  productSn?: string
  /** SKU 最低价（SPU 本身不存售价） */
  lowestPrice?: number | null
  pic?: string
  status?: number
  sale?: number
}

export interface Sku {
  id: number
  productId: number
  skuCode: string
  price?: number
  stock?: number
  spData?: string
}

export interface ProductDetailVO {
  product: Product
  skus: Sku[]
}
