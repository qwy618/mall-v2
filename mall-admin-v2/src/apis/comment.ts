import request from '@/utils/request'
import type { CommentListItem, CommentQuery } from '@/types/comment'

// 评价列表（分页 + 商品ID/状态/关键词筛选）
export function listComments(params: CommentQuery) {
  return request<{ list: CommentListItem[]; total: number }>({
    url: '/comment/list',
    method: 'get',
    params,
  })
}

// 审核：status=1 通过 / status=2 驳回
export function auditComment(id: number, status: number) {
  return request<number>({
    url: `/comment/audit/${id}`,
    method: 'post',
    params: { status },
  })
}

// 回复
export function replyComment(id: number, replyContent: string) {
  return request<number>({
    url: `/comment/reply/${id}`,
    method: 'post',
    data: { replyContent },
  })
}

// 删除
export function deleteComment(id: number) {
  return request<number>({
    url: `/comment/delete/${id}`,
    method: 'post',
  })
}
