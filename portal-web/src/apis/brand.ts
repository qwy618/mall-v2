import request from '@/utils/request'
import type { Brand } from '@/types/brand'

export function listBrands(categoryId?: number) {
  return request<Brand[]>({
    url: '/brand/list',
    method: 'get',
    params: categoryId != null ? { categoryId } : {},
  })
}
