// 管理员相关类型（登录 / 用户信息 / RBAC 用户·角色管理）

/** 登录入参 */
export interface AdminLoginParam {
  username: string
  password: string
}

/** 登录返回：前端约定 token = tokenHead + token */
export interface AdminLoginVO {
  tokenHead: string
  token: string
}

/** 当前管理员信息（与后端 AdminInfoVO 对齐） */
export interface AdminInfoVO {
  username: string
  nickName: string
  icon: string
  email: string
  roles: string[]
  /** 角色可见菜单并集（前端路由 name，逗号分隔后由后端拆成数组） */
  menuIds: string[]
}

/** 分页结果通用结构（对应后端 CommonPage） */
export interface PageResult<T> {
  list: T[]
  total: number
}

/** 管理员列表项 */
export interface UmsAdmin {
  id: number
  username: string
  nickName?: string
  email?: string
  icon?: string
  status?: number
  createTime?: string
  /** 角色 code 数组（后端 /admin/list 每项附带） */
  roles?: string[]
}

/** 角色列表项 */
export interface UmsRole {
  id: number
  name: string
  code: string
  description?: string
  status?: number
  sort?: number
  /** 该角色可见菜单（前端路由 name）；超级管理员可能为空=全部 */
  menuIds?: string[]
}

/** 新建/编辑管理员入参 */
export interface UmsAdminDTO {
  id?: number
  username: string
  password?: string
  nickName?: string
  email?: string
  status?: number
  roleIds?: number[]
}

/** 新建/编辑角色入参 */
export interface UmsRoleDTO {
  id?: number
  name: string
  code: string
  description?: string
  status?: number
  sort?: number
}

/** 分配管理员角色 */
export interface AdminRoleUpdateParam {
  adminId: number
  roleIds: number[]
}

/** 分配角色可见菜单 */
export interface RoleMenuUpdateParam {
  roleId: number
  menuIds: string[]
}

/** 菜单可选项（角色分配菜单时展示） */
export interface MenuOption {
  name: string
  title: string
}
