export interface Member {
  id: number
  phone?: string
  nickname?: string
  icon?: string
  status: number
  // ===== 会员成长体系（债务18）=====
  levelId?: number // 当前等级 id（member_level.id）
  integration?: number // 当前可用积分
  growth?: number // 成长值（决定等级）
  historyIntegration?: number // 累计获得积分（只增不减）
  createTime?: string
}

export interface LoginResult {
  token: string
  member: Member
}

// 会员等级配置（对齐后端 MemberLevel）
export interface MemberLevel {
  id: number
  name: string
  growthPoint: number
  integrationRate: number // 下单赠送积分倍率(%)：100=1倍
  discountRate: number // 会员折扣(%)：100=原价 98=98折
  note?: string
}

// 会员成长信息（对齐后端 MemberLevelVO，/member/level）
export interface MemberLevelVO {
  levelId?: number
  levelName: string
  integrationRate: number
  discountRate: number
  growth: number
  integration: number
  historyIntegration: number
  nextLevelName?: string | null
  nextGrowthPoint?: number | null
  growthGap?: number | null
  progress: number // 当前等级区间进度 0-100
}

// 积分流水（对齐后端 MemberIntegrationHistory）
export interface IntegrationHistory {
  id: number
  memberId?: number
  orderId?: number
  orderSn?: string
  changeType: number // 1下单赠送 2下单抵扣 3退货扣回 4管理员调整
  changeCount: number // 正=获得 负=消耗
  integrationAfter?: number
  operateMan?: string
  operateNote?: string
  createTime?: string
}

// 积分变动类型文案（与后端 MemberPointsService.TYPE_* 对应）
export const INTEGRATION_CHANGE_TEXT: Record<number, string> = {
  1: '订单赠送',
  2: '下单抵扣',
  3: '退货扣回',
  4: '管理员调整',
  5: '作废退回',
}

// 积分换算：100 积分 = 1 元（与后端 MemberPointsService.POINTS_PER_YUAN 一致）
export const POINTS_PER_YUAN = 100
