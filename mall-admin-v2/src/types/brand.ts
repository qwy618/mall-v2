/** 品牌实体：字段严格对齐后端 GET /brand/list 返回的 JSON */
export interface Brand {
  id: number
  name: string
  description: string
  logo: string
  sort: number
  createTime: string // 后端 LocalDateTime 序列化为 ISO 字符串，不是 Date
  updateTime: string
}

/** 新增/修改品牌的入参，对应后端 BrandParam（前端可传字段白名单） */
export interface BrandParam {
  name: string
  description?: string
  logo: string
  sort?: number
}
