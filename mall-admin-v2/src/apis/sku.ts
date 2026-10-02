import request from '@/utils/request'
import type { Sku, SkuParam } from '@/types/sku'
import type { CommonPage } from '@/types/common'

/**
 * 按商品查询 SKU 列表：GET /sku/list?productId=&pageNum=&pageSize=
 * productId 必传——SKU 从属于某个商品。
 */
export function listSkuByProduct(
  productId: number,
  pageNum: number,
  pageSize: number
): Promise<CommonPage<Sku>> {
  return request<CommonPage<Sku>>({
    url: '/sku/list',
    method: 'get',
    params: { productId, pageNum, pageSize },
  })
}

/** 新增 SKU：POST /sku/create，后端返回新增后的 id（同时生成 sku_code） */
export function createSku(data: SkuParam): Promise<number> {
  return request<number>({
    url: '/sku/create',
    method: 'post',
    data,
  })
}

/** 修改 SKU：POST /sku/update/{id}，传入 SkuParam 白名单字段，返回影响行数 */
export function updateSku(id: number, data: SkuParam): Promise<number> {
  return request<number>({
    url: `/sku/update/${id}`,
    method: 'post',
    data,
  })
}

/** 删除 SKU：POST /sku/delete/{id}，物理删除，返回影响行数 */
export function deleteSku(id: number): Promise<number> {
  return request<number>({
    url: `/sku/delete/${id}`,
    method: 'post',
  })
}
