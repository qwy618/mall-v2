import request from '@/utils/request'

// 上传文件到 MinIO，返回可访问的图片 URL
// POST /oss/upload (MultipartFile "file") -> CommonResult<String>
// 用 request 封装：自动带 token + 走 /api 前缀（proxy 剥离后命中后端 /oss/upload）
// 注意：不要手动设 Content-Type，axios 遇 FormData 会自动加 multipart/form-data + boundary
export function uploadOss(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request<string>({
    url: '/oss/upload',
    method: 'post',
    data: formData,
  })
}
