import request from '@/utils/request'
import type { Brand, BrandParam } from '@/types/brand'
import type { CommonPage } from '@/types/common'

/**
 * 分页查询品牌列表：GET /brand/list?pageNum=1&pageSize=5
 * 分页参数用 params（拼到 URL 上），不是 data（那会变成请求体）
 */
export function listBrand(pageNum: number, pageSize: number): Promise<CommonPage<Brand>> {
  return request<CommonPage<Brand>>({
    url: '/brand/list',
    method: 'get',
    params: { pageNum, pageSize },
  })
}

/** 新增品牌：POST /brand/create，后端返回新增后的 id（Long → 前端 number） */
export function createBrand(data: BrandParam): Promise<number> {
  return request<number>({
    url: '/brand/create',
    method: 'post',
    data,
  })
}

/** 品牌详情：GET /brand/{id}，返回 CommonResult<Brand> */
export function getBrandDetail(id: number): Promise<Brand> {
  return request<Brand>({
    url: `/brand/${id}`,
    method: 'get',
  })
}

/** 修改品牌：POST /brand/update/{id}，传入 BrandParam 白名单字段，返回影响行数 */
export function updateBrand(id: number, data: BrandParam): Promise<number> {
  return request<number>({
    url: `/brand/update/${id}`,
    method: 'post',
    data,
  })
}

/** 删除品牌：POST /brand/delete/{id}，物理删除，返回影响行数 */
export function deleteBrand(id: number): Promise<number> {
  return request<number>({
    url: `/brand/delete/${id}`,
    method: 'post',
  })
}
