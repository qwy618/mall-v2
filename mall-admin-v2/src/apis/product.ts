import request from '@/utils/request'
import type { Product, ProductParam } from '@/types/product'
import type { CommonPage } from '@/types/common'

/**
 * 分页查询商品列表：GET /product/list
 * 支持筛选：keyword（名称/货号模糊）、brandId、categoryId、status（1上架/0下架）
 * 后端 getList 已在阶段6 收尾补上 LambdaQueryWrapper 条件拼接。
 */
export interface ProductListParams {
  pageNum: number
  pageSize: number
  keyword?: string
  brandId?: number
  categoryId?: number
  status?: number
}
export function listProduct(params: ProductListParams): Promise<CommonPage<Product>> {
  return request<CommonPage<Product>>({
    url: '/product/list',
    method: 'get',
    params,
  })
}

/** 商品详情：GET /product/{id}，返回 CommonResult<Product> */
export function getProductDetail(id: number): Promise<Product> {
  return request<Product>({
    url: `/product/${id}`,
    method: 'get',
  })
}

/** 新增商品：POST /product/create，后端返回新增后的 id（同时生成 product_sn） */
export function createProduct(data: ProductParam): Promise<number> {
  return request<number>({
    url: '/product/create',
    method: 'post',
    data,
  })
}

/** 修改商品：POST /product/update/{id}，传入 ProductParam 白名单字段，返回影响行数 */
export function updateProduct(id: number, data: ProductParam): Promise<number> {
  return request<number>({
    url: `/product/update/${id}`,
    method: 'post',
    data,
  })
}

/** 删除商品：POST /product/delete/{id}，物理删除，返回影响行数 */
export function deleteProduct(id: number): Promise<number> {
  return request<number>({
    url: `/product/delete/${id}`,
    method: 'post',
  })
}
