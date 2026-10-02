import request from '@/utils/request'
import type { DashboardStats, DashboardTrend } from '@/types/dashboard'

// 获取后台首页统计数据
// GET /admin/dashboard/stats -> CommonResult<DashboardStatsVO>
// request 已自动解包 res.data，这里返回 T 即 DashboardStats
export function getDashboardStats() {
  return request<DashboardStats>({
    url: '/admin/dashboard/stats',
    method: 'get',
  })
}

// 获取看板时序（真实数据）
// GET /admin/dashboard/trend?days=7 -> CommonResult<DashboardTrendVO>
// days：统计窗口天数（默认 7，上限 90）
export function getDashboardTrend(days = 7) {
  return request<DashboardTrend>({
    url: '/admin/dashboard/trend',
    method: 'get',
    params: { days },
  })
}
