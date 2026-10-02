import request from '@/utils/request'

/**
 * 晒图上传：调 mall-portal 的 /upload 端点（返回 OSS 图片 URL 字符串）。
 * 注意：必须使用 mall-portal(8081) 的上传端点，不能复用 mall-admin(8080) 的（受 admin 鉴权保护）。
 */
export function uploadImage(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request<string>({
    url: '/upload',
    method: 'post',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
