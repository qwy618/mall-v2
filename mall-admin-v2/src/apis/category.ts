import request from '@/utils/request'
import type { Category, CategoryParam } from '@/types/category'
import type { CommonPage } from '@/types/common'

/**
 * 分页查询分类：GET /category/list
 * @param parentId 不传（undefined）查全部分类；传 0 查一级分类。
 *                对应后端 LambdaQueryWrapper.eq(parentId != null, ...)，
 *                正是“不传 vs 传 0”语义不同的实现点。
 */
export function listCategory(
  pageNum: number,
  pageSize: number,
  parentId?: number
): Promise<CommonPage<Category>> {
  return request<CommonPage<Category>>({
    url: '/category/list',
    method: 'get',
    params: { pageNum, pageSize, parentId },
  })
}

/** 分类详情：GET /category/{id} */
export function getCategoryDetail(id: number): Promise<Category> {
  return request<Category>({
    url: `/category/${id}`,
    method: 'get',
  })
}

/** 新增分类：POST /category/create，后端返回新增后的 id */
export function createCategory(data: CategoryParam): Promise<number> {
  return request<number>({
    url: '/category/create',
    method: 'post',
    data,
  })
}

/** 修改分类：POST /category/update/{id}，传入 CategoryParam 白名单字段，返回影响行数 */
export function updateCategory(id: number, data: CategoryParam): Promise<number> {
  return request<number>({
    url: `/category/update/${id}`,
    method: 'post',
    data,
  })
}

/** 删除分类：POST /category/delete/{id}，物理删除，返回影响行数 */
export function deleteCategory(id: number): Promise<number> {
  return request<number>({
    url: `/category/delete/${id}`,
    method: 'post',
  })
}
