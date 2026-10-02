/**
 * 商品图"内容盒"（去白边）元数据。
 *
 * 演示库里的商品图多为白底图，四周（尤其下方）常有大片纯白，直接按图片原始比例铺满容器
 * 就会出现"商品很小、一大片白"的观感。`src/data/pic-trim.json` 由离线脚本
 * `scripts/gen_pic_trim.py` 生成，记录了每张图真实内容盒在原图中的像素位置与尺寸；
 * 这里把它换算成便于渲染的分数形式。
 *
 * 未收录的图片（例如后台新上传的商品）返回 null，调用方用原图兜底 —— 不影响功能。
 */
import trimData from '@/data/pic-trim.json'

/** 原图坐标系下的内容盒；x0/y0/tw/th 为 0~1 分数，W/H 为原图像素尺寸 */
export interface PicCrop {
  x0: number
  y0: number
  tw: number
  th: number
  W: number
  H: number
}

const FULL: PicCrop = { x0: 0, y0: 0, tw: 1, th: 1, W: 0, H: 0 }

export function picMeta(pic?: string | null): PicCrop | null {
  if (!pic) return null
  const rec = (trimData as Record<string, number[]>)[pic]
  if (!Array.isArray(rec) || rec.length < 6) return null
  const [x, y, cw, ch, W, H] = rec
  if (!W || !H || !cw || !ch) return null
  return { x0: x / W, y0: y / H, tw: cw / W, th: ch / H, W, H }
}

/** 无裁剪数据时的整图内容盒（W/H 待探针图片加载后回填） */
export function fullCrop(W = 0, H = 0): PicCrop {
  return { ...FULL, W, H }
}
