import request from '@/utils/request'
import type { AttributeItem, AttributeParam, ProductAttribute } from '@/types/attribute'
import type { CommonPage } from '@/types/common'

/** 分页查询属性定义：GET /attribute/list，可按分类与类型过滤 */
export function listAttribute(params: {
  categoryId?: number
  type?: number
  pageNum: number
  pageSize: number
}): Promise<CommonPage<ProductAttribute>> {
  return request<CommonPage<ProductAttribute>>({
    url: '/attribute/list',
    method: 'get',
    params,
  })
}

/**
 * 按商品取属性定义（不分页）：GET /attribute/listByProduct
 * 用于「SKU 表单的规格下拉」和「商品参数表单」——二者都需要该商品所属分类下的属性。
 */
export function listAttributeByProduct(
  productId: number,
  type?: number
): Promise<ProductAttribute[]> {
  return request<ProductAttribute[]>({
    url: '/attribute/listByProduct',
    method: 'get',
    params: { productId, type },
  })
}

/** 新增属性：POST /attribute/create，返回新增后的 id */
export function createAttribute(data: AttributeParam): Promise<number> {
  return request<number>({
    url: '/attribute/create',
    method: 'post',
    data,
  })
}

/** 修改属性：POST /attribute/update/{id}，返回影响行数 */
export function updateAttribute(id: number, data: AttributeParam): Promise<number> {
  return request<number>({
    url: `/attribute/update/${id}`,
    method: 'post',
    data,
  })
}

/** 删除属性：POST /attribute/delete/{id}（属性已被取值使用时会返回业务错误） */
export function deleteAttribute(id: number): Promise<number> {
  return request<number>({
    url: `/attribute/delete/${id}`,
    method: 'post',
  })
}

/** 某商品的参数值：GET /attribute/productParams */
export function getProductParams(productId: number): Promise<AttributeItem[]> {
  return request<AttributeItem[]>({
    url: '/attribute/productParams',
    method: 'get',
    params: { productId },
  })
}

/** 覆盖式保存某商品的参数值：POST /attribute/productParams/{productId} */
export function saveProductParams(productId: number, items: AttributeItem[]): Promise<void> {
  return request<void>({
    url: `/attribute/productParams/${productId}`,
    method: 'post',
    data: items,
  })
}
