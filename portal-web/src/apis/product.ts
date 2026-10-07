import request from '@/utils/request'
import type { PageResult, Product, ProductDetailVO, SpecFilterGroup } from '@/types/product'

export function listProducts(params: {
  keyword?: string
  categoryId?: number
  brandId?: number
  /**
   * 规格筛选（P2）：`属性名:值|值,属性名:值`
   * 例 `颜色:黑色|白色,容量:256GB` —— 跨属性 AND、同属性多值 OR。
   * 后端会按当前分类把属性名解析成 attribute_id 再走 idx_attr_value。
   */
  attrs?: string
  pageNum?: number
  pageSize?: number
}) {
  return request<PageResult<Product>>({
    url: '/product/list',
    method: 'get',
    params,
  })
}

/**
 * 筛选面板数据源（P2）：某分类下的规格属性 → 可选值 → 命中商品数。
 * 不传 categoryId 则给全部规格属性。后端无数据时返回 []，面板据此整块隐藏。
 */
export function getSpecFilters(categoryId?: number) {
  return request<SpecFilterGroup[]>({
    url: '/product/spec-filters',
    method: 'get',
    params: { categoryId },
    // 接口未就绪 / 分类无规格时静默降级，不弹全局错误提示
    silent: true,
  })
}

export function getProduct(id: number) {
  return request<ProductDetailVO>({
    url: `/product/${id}`,
    method: 'get',
  })
}

// 相关推荐（详情页"猜你喜欢"）：同分类、按销量排序、排除自身
export function getSimilarProducts(id: number, pageSize = 8) {
  return request<Product[]>({
    url: `/product/similar/${id}`,
    method: 'get',
    params: { pageSize },
  })
}
