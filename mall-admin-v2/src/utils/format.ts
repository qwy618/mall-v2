/**
 * 展示层格式化工具（与后端序列化格式解耦的统一出口）。
 *
 * 后端 LocalDateTime 经 Jackson 序列化后形如 `2026-09-10T13:37:01`（带 T），
 * 直接渲染到页面会很难看，因此所有列表/详情的时间展示一律走本函数。
 * （如需全局改格式，只改这里一处即可。）
 */

/** 时间：`2026-09-10T13:37:01[.xxx]` → `2026-09-10 13:37:01`；空值 → '-' */
export function formatDateTime(t?: string | null): string {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}
