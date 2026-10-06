/**
 * 商品属性定义（债务 1）：字段严格对齐后端 GET /attribute/list 返回的 JSON。
 *
 * 两种属性粒度不同，不可混存：
 *   type=0 规格 —— SKU 级，影响价格与库存（颜色 / 容量），值存 sku_attribute_value
 *   type=1 参数 —— 商品级，仅展示（屏幕尺寸 / 上市年份），值存 product_attribute_value
 */
export interface ProductAttribute {
  id: number
  /** 归属分类：属性按分类隔离，同一个「颜色」在不同分类下是两条独立记录 */
  categoryId: number
  name: string
  type: number
  /** 0=手工录入 1=从列表选择 */
  inputType: number
  /** type=0 的候选值清单，逗号分隔（管理端下拉用） */
  inputList?: string
  sort: number
  createTime: string
}

/** 新增/修改属性入参：对齐后端 AttributeParam */
export interface AttributeParam {
  categoryId: number
  name: string
  type: number
  inputType?: number
  inputList?: string
  sort?: number
}

/** 一条商品参数值，对齐后端 AttributeItemVO */
export interface AttributeItem {
  attributeId: number
  /** 读接口会带回来；写接口不需要 */
  name?: string
  value: string
}
