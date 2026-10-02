import request from '@/utils/request'
import type { PageResult } from '@/types/product'
import type { IntegrationHistory, LoginResult, Member, MemberLevelVO } from '@/types/member'

// 登录：手机号 + 密码
export function login(phone: string, password: string) {
  return request<LoginResult>({
    url: '/member/login',
    method: 'post',
    params: { phone, password },
  })
}

// 注册：手机号（必填）+ 密码 + 昵称（可选）
export function register(phone: string, password: string, nickname?: string) {
  return request<number>({
    url: '/member/register',
    method: 'post',
    params: { phone, password, nickname },
  })
}

// 当前会员信息（手机号已脱敏，不含密码）
export function getMemberInfo() {
  return request<Member>({
    url: '/member/info',
    method: 'get',
  })
}

// 修改密码：需登录，传入原密码与新密码
export function updatePassword(oldPassword: string, newPassword: string) {
  return request<void>({
    url: '/member/updatePassword',
    method: 'post',
    params: { oldPassword, newPassword },
  })
}

// 更新头像：传入 OSS 图片 URL（通常由 /upload 获得）
export function updateMemberIcon(icon: string) {
  return request<null>({
    url: '/member/updateIcon',
    method: 'post',
    params: { icon },
  })
}

// 会员等级/成长信息（债务18）：等级名、权益、成长进度、积分余额
export function getMemberLevel() {
  return request<MemberLevelVO>({
    url: '/member/level',
    method: 'get',
  })
}

// 积分流水（债务18）：倒序分页
export function listIntegrationHistory(pageNum = 1, pageSize = 10) {
  return request<PageResult<IntegrationHistory>>({
    url: '/member/integration/list',
    method: 'get',
    params: { pageNum, pageSize },
  })
}
