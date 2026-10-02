// Dashboard 统计返回结构（对应后端 DashboardStatsVO）
// 后端各 count 用 Long，JSON 序列化为 number，前端用 number 接收
export interface DashboardStats {
  productTotal: number // 商品总数（product 物理删，全量）
  orderTotal: number // 订单总数（orders 逻辑删）
  orderToday: number // 今日订单数（create_time >= 今日 0 点）
  brandTotal: number // 品牌数（逻辑删）
  categoryTotal: number // 分类数（逻辑删）
  couponTotal: number // 优惠券总数（逻辑删）
  couponReceived: number // 优惠券已领取（coupon_history 全量）
  couponUsed: number // 优惠券已使用（coupon_history status=1）
}

// 看板时序（对应后端 DashboardTrendVO）
// 最近 days 天的每日订单数 + 销售额（真实数据，非示例）
export interface DashboardTrend {
  days: number
  dateList: string[] // 日期标签，如 ["09-17", "09-18"]
  orderCounts: number[] // 每日订单数
  orderAmounts: number[] // 每日销售额（元）
}
