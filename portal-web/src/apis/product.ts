import request from '@/utils/request'
import type { PageResult, Product, ProductDetailVO } from '@/types/product'

export function listProducts(params: {
  keyword?: string
  categoryId?: number
  brandId?: number
  pageNum?: number
  pageSize?: number
}) {
  return request<PageResult<Product>>({
    url: '/product/list',
    method: 'get',
    params,
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
