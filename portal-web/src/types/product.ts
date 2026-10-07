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

/** 一条商品参数（商品级、仅展示，如「屏幕尺寸: 6.1英寸」） */
export interface AttributeItem {
  attributeId: number
  name: string
  value: string
}

/** 一个规格属性的可选值集合（如 颜色 → [黑色, 白色]），来自各 SKU 的既有取值 */
export interface SpecOption {
  attributeId: number
  name: string
  values: string[]
}

/** 筛选面板里的一个可选值及其命中商品数（P2） */
export interface SpecFilterValue {
  value: string
  /** 该分类下拥有此值且已上架的商品数；仅面板展示，不参与筛选 */
  count: number
}

/** 筛选面板里的一个规格属性（如 颜色 → 黑色/白色…），供列表页反查筛选（P2） */
export interface SpecFilterGroup {
  attributeId: number
  name: string
  values: SpecFilterValue[]
}

export interface ProductDetailVO {
  product: Product
  skus: Sku[]
  /** 商品参数；债务1 之前这类信息无处可放，只能塞进副标题。后端无数据时返回 [] */
  attributes: AttributeItem[]
  /** 规格的可选值分组，供展示与后续「按规格筛选」使用 */
  specOptions: SpecOption[]
}
