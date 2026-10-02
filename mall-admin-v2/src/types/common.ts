/**
 * 与后端 com.macro.mall.common.CommonResult 一一对应的契约类型。
 *
 * 注意：后端 application.yml 配了 spring.jackson.default-property-inclusion: non_null，
 * 所以 data 为 null 时，这个 key 会整个消失（前端拿到 undefined），而不是 null。
 * 因此下面统一用可选属性，避免 TS 类型和运行时不一致。
 */
export interface CommonResult<T = unknown> {
  /** 业务码：200 成功，400 参数错误，404 数据不存在，500 系统异常 */
  code: number
  message: string
  data?: T
}

/** 与后端 com.macro.mall.common.CommonPage 一一对应 */
export interface CommonPage<T = unknown> {
  pageNum: number
  pageSize: number
  totalPage: number
  total: number
  list: T[]
}

/** 分页查询参数，对应后端的 pageNum / pageSize */
export interface PageQuery {
  pageNum: number
  pageSize: number
}
