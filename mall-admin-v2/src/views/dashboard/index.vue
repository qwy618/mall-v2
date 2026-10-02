<template>
  <div class="dashboard">
    <!-- 欢迎区 -->
    <el-card shadow="never" class="welcome">
      <div class="welcome__inner">
        <div class="welcome__text">
          <h2 class="welcome__title">Mall 后台管理</h2>
          <p class="welcome__desc">
            从 0 到 1 搭建的 mall 商城 · 优惠券 / 订单 / 评价模块已闭环。后端接口前缀
            <code>{{ baseApi }}</code> 经 Vite proxy 转发到 <code>{{ serverOrigin }}</code>。
          </p>
        </div>
        <div class="welcome__badge"><el-icon><DataLine /></el-icon></div>
      </div>
    </el-card>

    <!-- 数据图表：饼图 + 柱状图 + 折线图（ECharts） -->
    <el-card shadow="never" class="charts-card">
      <template #header>
        <span class="card-title">数据概览</span>
        <el-button text :loading="loading || trendLoading" class="refresh-btn" @click="refresh">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </template>

      <div v-loading="loading && !stats" class="charts">
        <!-- 饼图：优惠券状态分布 -->
        <div class="chart-block">
          <div class="chart-title">优惠券状态分布</div>
          <div ref="pieEl" class="chart-canvas"></div>
        </div>

        <!-- 柱状图：核心业务指标 -->
        <div class="chart-block">
          <div class="chart-title">核心业务指标</div>
          <div ref="barEl" class="chart-canvas"></div>
        </div>

        <!-- 折线图：近 N 日订单 / 销售额趋势（真实数据） -->
        <div class="chart-block">
          <div class="chart-title chart-title--row">
            <span>近 {{ trendDays }} 日订单 / 销售额趋势</span>
            <el-radio-group v-model="trendDays" size="small" @change="fetchTrend">
              <el-radio-button :value="7">7天</el-radio-button>
              <el-radio-button :value="30">30天</el-radio-button>
              <el-radio-button :value="90">90天</el-radio-button>
            </el-radio-group>
          </div>
          <div ref="lineEl" class="chart-canvas"></div>
        </div>
      </div>
    </el-card>

    <!-- 快捷入口：按当前用户权限过滤（与侧边栏同一套 canAccess） -->
    <el-card v-if="navs.length" shadow="never" class="nav-card">
      <template #header><span class="card-title">快捷入口</span></template>
      <el-row :gutter="16">
        <el-col v-for="nav in navs" :key="nav.path" :xs="12" :sm="8" :md="8" :lg="8">
          <div class="entry" :style="{ '--c': nav.color }" @click="go(nav.path)">
            <div class="entry__icon"><el-icon><component :is="nav.icon" /></el-icon></div>
            <div class="entry__body">
              <div class="entry__title">{{ nav.title }}</div>
              <div class="entry__sub">{{ nav.sub }}</div>
            </div>
            <el-icon class="entry__arrow"><ArrowRight /></el-icon>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-card shadow="never" class="roadmap">
      <template #header><span class="card-title">开发进度</span></template>
      <el-timeline>
        <el-timeline-item type="success">阶段2 后端骨架 · Brand / Category CRUD</el-timeline-item>
        <el-timeline-item type="success">阶段3 前端骨架 · Vue3 + TS + Vite + Element Plus</el-timeline-item>
        <el-timeline-item type="success">阶段4/5 登录 / JWT / RBAC 角色级</el-timeline-item>
        <el-timeline-item type="success">阶段6 商品管理（SPU + SKU）</el-timeline-item>
        <el-timeline-item type="success">阶段7 订单模块（状态机）</el-timeline-item>
        <el-timeline-item type="success">阶段8 优惠券模块（8 接口 + 前端页）</el-timeline-item>
        <el-timeline-item type="success">看板真实时序（订单数 + 销售额，7/30/90 天可切换）</el-timeline-item>
        <el-timeline-item>待推进：商品属性与规格筛选 / 库存锁定与释放 / 移动端</el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useRouter } from 'vue-router'
import {
  Box,
  Menu,
  Goods,
  List,
  Discount,
  Refresh,
  ArrowRight,
  DataLine,
} from '@element-plus/icons-vue'
import { getDashboardStats, getDashboardTrend } from '@/apis/dashboard'
import type { DashboardStats, DashboardTrend } from '@/types/dashboard'
import { useUserStore } from '@/stores/user'
import { canAccess } from '@/utils/permission'
import { routes } from '@/router'

const router = useRouter()
const userStore = useUserStore()
const serverOrigin = import.meta.env.VITE_SERVER_ORIGIN
const baseApi = import.meta.env.VITE_BASE_API

const go = (path: string) => router.push(path)

const stats = ref<DashboardStats | null>(null)
const loading = ref(false)

const fetchStats = async () => {
  loading.value = true
  try {
    stats.value = await getDashboardStats()
  } finally {
    loading.value = false
  }
}

// 时序（真实数据）：最近 trendDays 天的订单数 + 销售额
const trend = ref<DashboardTrend | null>(null)
const trendDays = ref(7)
const trendLoading = ref(false)

const fetchTrend = async () => {
  trendLoading.value = true
  try {
    trend.value = await getDashboardTrend(trendDays.value)
  } finally {
    trendLoading.value = false
  }
}

// 刷新：统计 + 时序一起拉
const refresh = async () => {
  loading.value = true
  trendLoading.value = true
  try {
    const [s, t] = await Promise.all([
      getDashboardStats(),
      getDashboardTrend(trendDays.value),
    ])
    stats.value = s
    trend.value = t
  } finally {
    loading.value = false
    trendLoading.value = false
  }
}

// ============ 快捷入口：按权限过滤 ============
// 把所有入口的「路由 name」映射出来，复用与侧边栏完全相同的 canAccess 逻辑，
// 保证「看不到的菜单 → 快捷入口也不展示」（修复：无权限卡片仍展示的问题）。
const routeByName = computed<Record<string, { meta?: { roles?: string[]; title?: string } }>>(() => {
  const m: Record<string, { meta?: { roles?: string[]; title?: string } }> = {}
  const root = routes.find((r) => r.path === '/')
  ;(root?.children ?? []).forEach((c) => {
    if (c.name) m[String(c.name)] = c as never
  })
  return m
})

interface Nav {
  path: string
  name: string
  title: string
  sub: string
  icon: unknown
  color: string
}
const allNavs: Nav[] = [
  { path: '/brand', name: 'Brand', title: '品牌管理', sub: 'Brand CRUD', icon: Box, color: '#b5633f' },
  { path: '/category', name: 'Category', title: '商品分类', sub: 'Category', icon: Menu, color: '#c08a3e' },
  { path: '/product', name: 'Product', title: '商品管理', sub: 'SPU + SKU', icon: Goods, color: '#c0744f' },
  { path: '/order', name: 'Order', title: '订单管理', sub: '状态机', icon: List, color: '#5a8a6a' },
  { path: '/coupon', name: 'Coupon', title: '优惠券管理', sub: '8 接口', icon: Discount, color: '#a5623f' },
]

const navs = computed(() =>
  allNavs.filter((n) => {
    const r = routeByName.value[n.name]
    return canAccess(r?.meta?.roles, userStore.userInfo.roles, userStore.userInfo.menus, n.name)
  })
)

// ============ 图表数据 ============
// 饼图：优惠券 已使用 / 已领取未用 / 未领取
const couponSegments = computed(() => {
  if (!stats.value) return []
  const total = stats.value.couponTotal || 0
  const used = stats.value.couponUsed || 0
  const received = stats.value.couponReceived || 0
  const receivedUnused = Math.max(0, received - used)
  const unReceived = Math.max(0, total - received)
  return [
    { name: '已使用', value: used, color: '#c0744f' },
    { name: '已领取未用', value: receivedUnused, color: '#c08a3e' },
    { name: '未领取', value: unReceived, color: '#e3cfba' },
  ].filter((s) => s.value > 0)
})

// 柱状图：核心业务指标
const barMetrics = computed(() => {
  if (!stats.value) return []
  return [
    { label: '商品总数', value: stats.value.productTotal || 0, color: '#c0744f' },
    { label: '订单累计', value: stats.value.orderTotal || 0, color: '#b5633f' },
    { label: '今日订单', value: stats.value.orderToday || 0, color: '#5a8a6a' },
    { label: '品牌数', value: stats.value.brandTotal || 0, color: '#c08a3e' },
    { label: '分类数', value: stats.value.categoryTotal || 0, color: '#a89478' },
  ]
})

// 折线图数据来自真实接口 trend（见 renderCharts 的 line 分支），不再使用示例数据

// ============ ECharts 渲染 ============
type EC = ReturnType<typeof echarts.init>
const pieEl = ref<HTMLElement>()
const barEl = ref<HTMLElement>()
const lineEl = ref<HTMLElement>()
let pieChart: EC | null = null
let barChart: EC | null = null
let lineChart: EC | null = null

function renderCharts() {
  // 饼图 + 柱状图依赖 stats
  if (stats.value) {
    if (pieEl.value) {
      pieChart = pieChart ?? echarts.init(pieEl.value)
      pieChart.setOption({
        color: couponSegments.value.map((s) => s.color),
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { bottom: 0, icon: 'circle', itemWidth: 10, itemHeight: 10, textStyle: { color: '#a89478' } },
        series: [
          {
            type: 'pie',
            radius: ['42%', '68%'],
            center: ['50%', '44%'],
            avoidLabelOverlap: true,
            itemStyle: { borderColor: '#fffdfb', borderWidth: 2, borderRadius: 6 },
            label: { show: true, formatter: '{b}\n{c}', fontSize: 12, color: '#a89478' },
            labelLine: { length: 12, length2: 10 },
            data: couponSegments.value.map((s) => ({ name: s.name, value: s.value })),
          },
        ],
      })
    }

    if (barEl.value) {
      barChart = barChart ?? echarts.init(barEl.value)
      barChart.setOption({
        grid: { left: 8, right: 16, top: 24, bottom: 28, containLabel: true },
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: {
          type: 'category',
          data: barMetrics.value.map((m) => m.label),
          axisLabel: { color: '#a89478', fontSize: 11, interval: 0 },
          axisLine: { lineStyle: { color: '#ece2d8' } },
          axisTick: { show: false },
        },
        yAxis: {
          type: 'value',
          axisLabel: { color: '#a89478' },
          splitLine: { lineStyle: { color: '#f2e9de' } },
        },
        series: [
          {
            type: 'bar',
            barWidth: '46%',
            data: barMetrics.value.map((m) => m.value),
            itemStyle: {
              borderRadius: [6, 6, 0, 0],
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#d08a63' },
                { offset: 1, color: '#c0744f' },
              ]),
            },
          },
        ],
      })
    }
  }

  // 折线图依赖真实时序 trend（订单数 + 销售额，双 Y 轴）
  if (trend.value && lineEl.value) {
    lineChart = lineChart ?? echarts.init(lineEl.value)
    lineChart.setOption({
      grid: { left: 8, right: 16, top: 30, bottom: 42, containLabel: true },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, left: 'center', icon: 'circle', itemWidth: 10, itemHeight: 10, textStyle: { color: '#a89478' } },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: trend.value.dateList,
        axisLabel: { color: '#a89478', fontSize: 11 },
        axisLine: { lineStyle: { color: '#ece2d8' } },
        axisTick: { show: false },
      },
      yAxis: [
        {
          type: 'value',
          name: '订单数',
          nameGap: 12,
          nameTextStyle: { color: '#a89478', align: 'left' },
          axisLabel: { color: '#a89478' },
          splitLine: { lineStyle: { color: '#f2e9de' } },
        },
        {
          type: 'value',
          name: '销售额(元)',
          nameGap: 12,
          nameTextStyle: { color: '#a89478', align: 'right' },
          axisLabel: { color: '#a89478' },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '订单数',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          yAxisIndex: 0,
          data: trend.value.orderCounts,
          itemStyle: { color: '#5a8a6a' },
          lineStyle: { width: 3, color: '#5a8a6a' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(90,138,106,0.26)' },
              { offset: 1, color: 'rgba(90,138,106,0.02)' },
            ]),
          },
        },
        {
          name: '销售额',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          yAxisIndex: 1,
          data: trend.value.orderAmounts,
          itemStyle: { color: '#c0744f' },
          lineStyle: { width: 3, color: '#c0744f' },
        },
      ],
    })
  }
}

const onResize = () => {
  pieChart?.resize()
  barChart?.resize()
  lineChart?.resize()
}

// stats / trend 变化后重绘；首次挂载也尝试绘制（缓存命中时）
watch([stats, trend], () => nextTick(renderCharts), { flush: 'post' })

onMounted(() => {
  window.addEventListener('resize', onResize)
  if (stats.value) nextTick(renderCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  pieChart?.dispose()
  barChart?.dispose()
  lineChart?.dispose()
})

onMounted(fetchStats)
onMounted(fetchTrend)
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--admin-text);
  font-family: var(--mall-font-serif);
}

.charts-card :deep(.el-card__header),
.nav-card :deep(.el-card__header),
.roadmap :deep(.el-card__header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.refresh-btn {
  margin: 0;
  padding: 0;
}

.welcome {
  background: linear-gradient(120deg, #fdf8f1 0%, #f7ece0 55%, #f3e2d0 100%);
  border: 1px solid #ecdccb;
  color: var(--admin-text);
}

.welcome :deep(.el-card__body) {
  padding: 22px 28px;
}

.welcome__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.welcome__title {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
  color: var(--admin-text);
  font-family: var(--mall-font-serif);
  letter-spacing: 0.5px;
}

.welcome__desc {
  margin: 0;
  color: var(--admin-text-regular);
  line-height: 1.8;
  font-size: 13px;
}

.welcome__desc code {
  background: rgba(192, 116, 79, 0.12);
  color: var(--mall-price);
  padding: 2px 6px;
  border-radius: 4px;
}

.welcome__badge {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: rgba(192, 116, 79, 0.14);
  border: 1px solid #e6cdb5;
  color: var(--mall-primary);
  font-size: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* ---------- 图表区 ---------- */
.charts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.chart-block {
  min-width: 0;
  background: #fdf9f4;
  border: 1px solid var(--admin-border);
  border-radius: var(--admin-radius-lg);
  padding: 14px 10px 6px;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--admin-text);
  font-family: var(--mall-font-serif);
  margin-bottom: 6px;
  padding-left: 4px;
}

.chart-title--row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-left: 4px;
}

.chart-note {
  font-size: 11px;
  font-weight: 400;
  color: var(--admin-text-light);
}

.chart-canvas {
  width: 100%;
  height: 240px;
}

/* ---------- 快捷入口 ---------- */
.entry {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border-radius: var(--admin-radius-lg);
  background: var(--admin-card);
  border: 1px solid var(--admin-border);
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.entry:hover {
  box-shadow: var(--admin-shadow);
  border-color: #ddbba0;
  transform: translateY(-2px);
}

.entry__icon {
  width: 46px;
  height: 46px;
  border-radius: 12px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: var(--c, var(--mall-primary));
  background: color-mix(in srgb, var(--c, #c0744f) 12%, #fffdfb);
  border: 1px solid color-mix(in srgb, var(--c, #c0744f) 26%, #fffdfb);
}

.entry__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--admin-text);
}

.entry__sub {
  color: var(--admin-text-light);
  font-size: 12px;
  margin-top: 4px;
}

.entry__arrow {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--admin-text-light);
}

.entry:hover .entry__arrow {
  color: var(--mall-primary);
}

@media (max-width: 900px) {
  .charts {
    grid-template-columns: 1fr;
  }
}
</style>
