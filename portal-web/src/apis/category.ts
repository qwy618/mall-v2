import request from '@/utils/request'
import type { CategoryNode } from '@/types/category'

export function listCategories() {
  return request<CategoryNode[]>({
    url: '/category/list',
    method: 'get',
  })
}
