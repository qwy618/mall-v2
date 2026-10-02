import request from '@/utils/request'
import type { PageResult } from '@/types/product'
import type {
  CommentSubmitParam,
  ProductCommentVO,
  CommentStats,
  MyComment,
} from '@/types/comment'

// 提交评价（需登录；后端校验订单项归属、订单已完成、未重复评价）
export function submitComment(param: CommentSubmitParam) {
  return request<number>({
    url: '/comment/submit',
    method: 'post',
    data: param,
  })
}

// 商品评价列表（公开，仅返回审核通过 status=1）
export function listProductComments(productId: number, pageNum = 1, pageSize = 10) {
  return request<PageResult<ProductCommentVO>>({
    url: `/comment/product/${productId}`,
    method: 'get',
    params: { pageNum, pageSize },
  })
}

// 商品评分统计（平均星、各星级数量、总数，仅 status=1）
export function getCommentStats(productId: number) {
  return request<CommentStats>({
    url: `/comment/product/${productId}/stats`,
    method: 'get',
  })
}

// 我的评价（登录，含全部状态，便于「待审核/被驳回」提示）
export function listMyComments(pageNum = 1, pageSize = 10) {
  return request<PageResult<MyComment>>({
    url: '/comment/mine',
    method: 'get',
    params: { pageNum, pageSize },
  })
}
