# 商品评价系统 · 设计与落地指南

> 状态：设计已定，DDL + mbg 样板已落盘，前端由 AI 直写，后端业务 Java 待用户手写（或授权 AI 落盘参考实现）。
> 红线：后端业务 Java（Controller/Service/Impl/VO/DTO）由用户手写 + AI 审查；DDL / mbg 样板 AI 已落盘；前端 AI 直写。

## 1. 设计决策（已与用户确认）
- **粒度**：按订单项（一个订单里的每个商品各评一次）。评价表主关联 `order_item_id`，冗余 `product_id/sku_id/order_id/order_sn/会员信息`。
- **评分模型**：整体单星（1-5）+ 文字内容 + 多图晒单（图片 URL 存 JSON 数组，上传到阿里云 OSS）。
- **审核**：需要后台审核。`status` 状态机 `0 待审核 / 1 通过 / 2 驳回`，仅 `status=1` 在商品详情页公开展示。

## 2. 数据库（已落盘 `sql/review_comment.sql`，幂等可重复执行）
- 新建 `comment` 表：核心字段 `order_item_id(唯一, 防重复评价) / product_id / sku_id / member_id / star / content / pics(JSON) / anonymous / status / reply_content / reply_time`。
- `order_item` 追加 `comment_status tinyint(0未评价 1已评价)`，便于订单列表直接显示「评价/已评价」无需联表。

## 3. 接口契约

### 3.1 C 端（mall-portal，除列表/统计外均需登录）
| 方法 | 路径 | 说明 | 关键校验 |
|---|---|---|---|
| POST | `/upload` | 晒图上传（mall-portal 新增，复用阿里云 OSS，返回 URL 字符串） | 登录 |
| POST | `/comment/submit` | 提交评价 | 见 §5.1 |
| GET  | `/comment/product/{productId}` | 商品评价列表（**公开**，仅 `status=1`，分页） | 无 |
| GET  | `/comment/product/{productId}/stats` | 评分统计（平均星、各星级数量、总数，仅 `status=1`） | 无 |
| GET  | `/comment/mine` | 我的评价（登录，含全部状态，便于「待审核/被驳回」提示） | 登录 |

### 3.2 管理端（mall-admin，需 admin 角色或 Comment 菜单权限）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET  | `/comment/list` | 列表（分页；支持 `productId / status / keyword(昵称或商品名)` 筛选） |
| POST | `/comment/audit/{id}` | 审核：`?status=1` 通过 / `?status=2` 驳回 |
| POST | `/comment/reply/{id}` | 回复：`{ replyContent }` |
| POST | `/comment/delete/{id}` | 删除（物理删，谨慎；也可改逻辑删，按需） |

## 4. 后端类清单（用户手写 + AI 审查）

### 4.1 mall-portal
- `controller/CommentController.java`（`@RequestMapping("/comment")` + 独立的 `FileController`/`OssController` 提供 `/upload`）
- `service/CommentService.java` + `service/Impl/CommentServiceImpl.java`
- `dto/CommentSubmitParam.java`：`orderItemId, star, content, pics(List<String>), anonymous`
- `vo/ProductCommentVO.java`：`id, star, content, pics, anonymous, nickname, icon, createTime`（匿名时昵称显示「匿名用户」）
- `vo/CommentStatsVO.java`：`avgStar, total, fiveStar, fourStar, threeStar, twoStar, oneStar`

### 4.2 mall-admin
- `controller/CommentController.java`（`@RequestMapping("/comment")`，方法加 `@PreAuthorize("hasRole('admin')")` 或走菜单拦截器）
- `service/CommentService.java` + `service/Impl/CommentServiceImpl.java`
- `vo/CommentListItemVO.java`：`id, productName, productPic, nickname, star, content, pics, status, replyContent, createTime`（含 orderSn 便于定位）

> mbg 样板（`model/Comment.java` + `mapper/CommentMapper.java`）已由 AI 落盘到 `mall-mbg`，后端业务代码直接注入 `CommentMapper` 即可。

## 5. 关键业务逻辑（伪代码）

### 5.1 提交评价 `submit`
```
memberId = 当前登录会员
oi = orderItemMapper.selectById(param.orderItemId)
if oi == null or oi.memberId != memberId: 抛 "无权评价该订单"
order = ordersMapper.selectById(oi.orderId)
if order.status != 3(已完成/已收货): 抛 "订单未完成，暂不能评价"
if commentMapper.existsByOrderItemId(param.orderItemId): 抛 "该商品已评价"  // 双保险，DB 还有唯一约束
member = memberMapper.selectById(memberId)
c = Comment{ orderItemId, orderId, orderSn, productId, skuId,
             productName=oi.productName, productPic=oi.productPic,
             memberId, star, content, pics=JSON(param.pics),
             anonymous, status=0(待审核), createTime=now }
if anonymous==1: c.memberNickname=null; c.memberIcon=null
else: c.memberNickname=member.nickname; c.memberIcon=member.icon
commentMapper.insert(c)
orderItemMapper.update: comment_status=1 where id=oi.id   // 标记已评价
return success
```

### 5.2 审核 / 回复
- `audit`：`update comment set status=? where id=?`（仅待审核可转变；驳回可带原因记录到 reply_content 或单独字段，按需）
- `reply`：`update comment set reply_content=?, reply_time=now where id=?`

## 6. 前端清单（AI 直写）

### 6.1 C 端 portal-web
- `src/types/comment.ts`：`Comment, CommentSubmitParam, CommentStats` 类型
- `src/apis/comment.ts`：`submitComment, listProductComments, getCommentStats, listMyComments`
- `src/apis/upload.ts`：`uploadImage(file)` → 调 `/upload`
- `src/views/review/submit.vue`（路由 `/review/submit?orderItemId=`）→ 打星 + 文字 + 多图上传 + 匿名开关；提交后回退并提示
- 「我的订单」页（现有订单列表）：对 `status=3 且 comment_status=0` 的订单项显示「评价」按钮，跳 `/review/submit`
- 商品详情页（`views/product/index.vue`）：新增「评价」Tab，展示 `stats`（平均星 + 分布）+ 评价列表（分页）

### 6.2 管理端 admin-v2
- `src/types/comment.ts` + `src/apis/comment.ts`：`listComments, auditComment, replyComment, deleteComment`
- `src/views/comment/index.vue`：表格（商品图/名、会员、星级、内容、状态标签）+ 筛选（商品ID/状态/关键词）+ 审核通过/驳回按钮 + 回复对话框 + 删除
- `src/router/index.ts`：新增 `{ path:'comment', name:'Comment', component:..., meta:{...} }` 且 **加入菜单（与 Brand/Coupon 同级）** —— 这样 RBAC 菜单选项里才会出现「评价管理」

### 6.3 RBAC 注意点
- 新增的 `Comment` 路由需设为菜单项（`meta` 标记为可配菜单），否则角色分配页看不到它、无法授权。
- 给需要看评价管理的角色（如 admin）在 `ums_role.menu_ids` 追加 `Comment`（或前端分配菜单时勾选）。

## 7. 验收标准
1. **C 端提交流程**：下单 → 确认收货（status=3）→ 我的订单出现「评价」→ 打星+写内容+传图+可匿名 → 提交成功 → 该订单项显示「已评价」，再次进入提示已评。
2. **审核前不公开**：提交后商品详情页评价列表**不显示**该条（status=0）。
3. **管理端审核**：admin 登录 → 评价管理看到待审核条目 → 通过 → 商品详情页出现该评价；驳回则不出现。
4. **回复**：管理端回复后，C 端我的评价/商品详情页显示商家回复。
5. **防越权**：A 会员不能评价 B 会员的订单项（提交返错误）；未收货订单不能评价。
6. **统计正确**：商品评价统计的平均星与各星级数量随审核通过的评价实时更新。

## 8. 排错
- 提交报「订单未完成」：确认订单 `status=3`（确认收货后）。
- 商品页评价不显示：检查 `status=1`，且 C 端列表接口过滤了非通过状态。
- 管理端看不到「评价管理」菜单：确认 `Comment` 路由已设为菜单 + 角色 `menu_ids` 含 `Comment`。
- 上传图片 401：C 端 `/upload` 必须在 mall-portal（8081）新增，不能复用 admin(8080) 的（受 admin 鉴权保护）。
