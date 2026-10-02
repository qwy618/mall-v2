import request from '@/utils/request'
import type {
  AdminLoginParam,
  AdminLoginVO,
  AdminInfoVO,
  PageResult,
  UmsAdmin,
  UmsRole,
  UmsAdminDTO,
  UmsRoleDTO,
  AdminRoleUpdateParam,
  RoleMenuUpdateParam,
} from '@/types/admin'

/** 登录：返回 tokenHead + token */
export function adminLoginAPI(loginParam: AdminLoginParam) {
  return request<AdminLoginVO>({
    url: '/admin/login',
    method: 'post',
    data: loginParam,
  })
}

/** 获取当前登录管理员信息（需带 token） */
export function getAdminInfoAPI() {
  return request<AdminInfoVO>({
    url: '/admin/info',
    method: 'post',
  })
}

/* ===================== 用户管理（RBAC） ===================== */

/** 分页查询管理员 */
export function listAdminsAPI(params: {
  keyword?: string
  pageNum?: number
  pageSize?: number
}) {
  return request<PageResult<UmsAdmin>>({
    url: '/admin/list',
    method: 'get',
    params,
  })
}

/** 新建管理员 */
export function createAdminAPI(data: UmsAdminDTO) {
  return request<number>({ url: '/admin/create', method: 'post', data })
}

/** 编辑管理员 */
export function updateAdminAPI(data: UmsAdminDTO) {
  return request<number>({ url: '/admin/update', method: 'post', data })
}

/** 删除管理员 */
export function deleteAdminAPI(id: number) {
  return request<number>({ url: `/admin/delete/${id}`, method: 'post' })
}

/** 启用/禁用管理员 */
export function updateAdminStatusAPI(id: number, status: number) {
  return request<number>({ url: `/admin/updateStatus/${id}`, method: 'post', data: { status } })
}

/** 分配管理员角色 */
export function updateAdminRoleAPI(param: AdminRoleUpdateParam) {
  return request<number>({ url: '/admin/role/update', method: 'post', data: param })
}

/** 查询某管理员已分配角色 id 列表 */
export function getAdminRolesAPI(adminId: number) {
  return request<number[]>({ url: `/admin/role/${adminId}`, method: 'get' })
}

/* ===================== 角色管理（RBAC） ===================== */

/** 查询全部角色 */
export function listRolesAPI() {
  return request<UmsRole[]>({ url: '/role/list', method: 'get' })
}

/** 新建角色 */
export function createRoleAPI(data: UmsRoleDTO) {
  return request<number>({ url: '/role/create', method: 'post', data })
}

/** 编辑角色 */
export function updateRoleAPI(data: UmsRoleDTO) {
  return request<number>({ url: '/role/update', method: 'post', data })
}

/** 删除角色 */
export function deleteRoleAPI(id: number) {
  return request<number>({ url: `/role/delete/${id}`, method: 'post' })
}

/** 分配角色可见菜单 */
export function updateRoleMenusAPI(param: RoleMenuUpdateParam) {
  return request<number>({ url: '/role/updateMenus', method: 'post', data: param })
}
