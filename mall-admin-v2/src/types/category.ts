/** 商品分类实体：字段严格对齐后端 GET /category/list 返回的 JSON */
export interface Category {
  id: number
  name: string
  parentId: number | null // 一级分类的 parentId 为 0，理论上可为 null
  level: number
  sort: number
  icon: string
  showStatus: number // 0=隐藏, 1=显示
  createTime: string // LocalDateTime 序列化为 ISO 字符串
  updateTime: string
}

/** 新增分类入参：对齐后端 CategoryParam（前端可传字段白名单） */
export interface CategoryParam {
  name: string
  parentId: number
  level: number
  sort: number
  icon?: string // 可选
  showStatus: number
}
