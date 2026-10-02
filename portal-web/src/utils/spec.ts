/**
 * 把后端的规格字段（sku.sp_data / order_item.sp_data）格式化成可读文本。
 *
 * 后端实际存法是一个 JSON 数组字符串，例如：
 *   [{"key":"颜色","value":"黑色"},{"key":"内存","value":"8+128G"}]
 *
 * 历史坑：订单页曾直接 `Object.entries(JSON.parse(spData))`，
 * 数组会被当成对象遍历 -> 得到 ['0', {...}] -> 渲染出 "0:[object Object]"。
 * 这里统一处理，所有页面共用同一份逻辑，避免各写各的再次踩坑。
 *
 * 兼容形态：
 *   1) [{ key, value }, ...]        —— mall 实际存法
 *   2) ["颜色:黑色", "内存:8G"]      —— 字符串数组
 *   3) { 颜色: "黑色", 内存: "8G" }  —— 普通对象
 *   4) 非法 JSON                    —— 原样返回
 */
export function formatSpec(spData?: string | null): string {
  if (spData === null || spData === undefined) return ''
  const text = String(spData).trim()
  if (!text) return ''

  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    // 不是合法 JSON，按原文展示（例如后端存的就是 "黑色 8+128G"）
    return text
  }

  // 形态 1/2：数组
  if (Array.isArray(parsed)) {
    return parsed
      .map((item) => {
        if (item && typeof item === 'object') {
          const o = item as Record<string, unknown>
          const key = o.key ?? o.name ?? ''
          const value = o.value ?? o.val ?? ''
          if (key !== '' && value !== '') return `${key}:${value}`
          if (value !== '') return String(value)
          // 兜底：把对象拍平成 k:v（值仍是对象则 JSON 化，杜绝 [object Object]）
          return Object.entries(o)
            .map(([k, v]) => `${k}:${toText(v)}`)
            .join(' ')
        }
        return String(item)
      })
      .filter((s) => s.trim() !== '')
      .join('  ')
  }

  // 形态 3：普通对象
  if (parsed && typeof parsed === 'object') {
    return Object.entries(parsed as Record<string, unknown>)
      .map(([k, v]) => `${k}:${toText(v)}`)
      .join('  ')
  }

  // 形态 3：标量（数字 / 布尔 / 字符串）
  return String(parsed)
}

/** 把任意值转成可读文本；对象降级为 JSON，避免出现 [object Object] */
function toText(v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
