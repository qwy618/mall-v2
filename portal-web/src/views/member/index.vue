<template>
  <div class="member">
    <!-- 用户卡片（京东红） -->
    <section class="profile">
      <div class="profile__bg" />
      <div class="profile__inner">
        <label class="avatar" :class="{ 'avatar--busy': avatarUploading }">
          <img v-if="member?.icon" :src="member.icon" alt="头像" />
          <span v-else>{{ avatarText }}</span>
          <span class="avatar__mask">
            <el-icon><Camera /></el-icon>
            <i class="avatar__tip">更换</i>
          </span>
          <input ref="fileInput" type="file" accept="image/*" hidden @change="onAvatarChange" />
        </label>
        <div class="profile__info">
          <div class="profile__name">
            {{ member?.nickname || userStore.nickname || '尊贵会员' }}
            <span class="profile__vip">{{ levelInfo?.levelName || '普通会员' }}</span>
          </div>
          <div class="profile__phone">{{ displayPhone }}</div>
          <div class="profile__meta">注册时间：{{ registerTime }}</div>
        </div>
        <router-link to="/member/change-password" class="profile__setting">
          <el-icon><Setting /></el-icon> 账户设置
        </router-link>
      </div>
    </section>

    <!-- 会员成长（债务18：等级 / 成长值 / 积分） -->
    <section v-if="levelInfo" class="card">
      <div class="card__head">
        <h3 class="card__title">会员成长</h3>
        <router-link to="/member/integration" class="card__more">积分明细 ›</router-link>
      </div>
      <div class="growth">
        <div class="growth__item">
          <div class="growth__num">{{ levelInfo.integration }}</div>
          <div class="growth__label">可用积分</div>
        </div>
        <div class="growth__item">
          <div class="growth__num">{{ levelInfo.growth }}</div>
          <div class="growth__label">成长值</div>
        </div>
        <div class="growth__item">
          <div class="growth__num">
            {{ levelInfo.discountRate >= 100 ? '无' : levelInfo.discountRate / 10 + ' 折' }}
          </div>
          <div class="growth__label">会员折扣</div>
        </div>
        <div class="growth__item">
          <div class="growth__num">{{ (levelInfo.integrationRate / 100).toFixed(1) }}x</div>
          <div class="growth__label">积分倍率</div>
        </div>
      </div>
      <div class="growth__bar">
        <div class="growth__bar-top">
          <span>当前 <b>{{ levelInfo.levelName }}</b></span>
          <span v-if="levelInfo.nextLevelName">
            距 {{ levelInfo.nextLevelName }} 还差 <b>{{ levelInfo.growthGap }}</b> 成长值
          </span>
          <span v-else>已是最高等级</span>
        </div>
        <div class="growth__track">
          <div class="growth__fill" :style="{ width: levelInfo.progress + '%' }" />
        </div>
      </div>
    </section>

    <!-- 我的订单 -->
    <section class="card">
      <div class="card__head">
        <h3 class="card__title">我的订单</h3>
        <router-link to="/order/list" class="card__more">查看全部 ›</router-link>
      </div>
      <div class="order-grid">
        <div
          v-for="t in orderTabs"
          :key="String(t.status)"
          class="order-item"
          @click="goOrder(t.status)"
        >
          <el-icon class="order-item__icon" :size="26"><component :is="t.icon" /></el-icon>
          <span class="order-item__label">{{ t.label }}</span>
        </div>
      </div>
    </section>

    <!-- 账户管理 -->
    <section class="card">
      <div class="card__head">
        <h3 class="card__title">账户管理</h3>
      </div>
      <div class="tool-grid">
        <div
          v-for="item in toolList"
          :key="item.label"
          class="tool-item"
          @click="onTool(item)"
        >
          <div class="tool-item__icon" :style="{ color: item.color }">
            <el-icon :size="24"><component :is="item.icon" /></el-icon>
          </div>
          <span class="tool-item__label">{{ item.label }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Money,
  Box,
  Van,
  EditPen,
  CircleClose,
  Ticket,
  Lock,
  Location,
  Star,
  SwitchButton,
  Setting,
  Camera,
  RefreshLeft,
  Coin,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { getMemberInfo, getMemberLevel, updateMemberIcon } from '@/apis/member'
import { uploadImage } from '@/apis/upload'
import type { Member, MemberLevelVO } from '@/types/member'

const router = useRouter()
const userStore = useUserStore()
const { nickname, phone } = storeToRefs(userStore)

const member = ref<Member | null>(null)
// 会员成长信息（债务18）：等级 / 成长值进度 / 积分
const levelInfo = ref<MemberLevelVO | null>(null)

const avatarText = computed(() => (member.value?.nickname || nickname.value || 'M').charAt(0).toUpperCase())
const displayPhone = computed(() => member.value?.phone || phone.value || '—')
const registerTime = computed(() => {
  const t = member.value?.createTime
  return t ? t.replace('T', ' ').slice(0, 10) : '—'
})

// 头像上传
const fileInput = ref<HTMLInputElement | null>(null)
const avatarUploading = ref(false)
async function onAvatarChange(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    target.value = ''
    return
  }
  avatarUploading.value = true
  try {
    const url = await uploadImage(file)
    await updateMemberIcon(url)
    if (member.value) member.value = { ...member.value, icon: url }
    userStore.setIcon(url)
    ElMessage.success('头像已更新')
  } catch (err: any) {
    ElMessage.error(err?.message || '头像上传失败')
  } finally {
    avatarUploading.value = false
    target.value = ''
  }
}

interface OrderTab {
  status: number
  label: string
  icon: unknown
}
const orderTabs: OrderTab[] = [
  { status: 0, label: '待支付', icon: Money },
  { status: 1, label: '待发货', icon: Box },
  { status: 2, label: '待收货', icon: Van },
  { status: 3, label: '待评价', icon: EditPen },
  { status: 4, label: '已取消', icon: CircleClose },
  { status: 5, label: '已失效', icon: CircleClose },
]

interface Tool {
  label: string
  icon: unknown
  color: string
  action: 'coupon' | 'password' | 'address' | 'favorite' | 'return' | 'integration' | 'logout'
}
const toolList: Tool[] = [
  { label: '我的优惠券', icon: Ticket, color: '#e8752a', action: 'coupon' },
  { label: '积分明细', icon: Coin, color: '#d2a14f', action: 'integration' },
  { label: '修改密码', icon: Lock, color: '#9c7a4d', action: 'password' },
  { label: '收货地址', icon: Location, color: '#7a9c6b', action: 'address' },
  { label: '我的收藏', icon: Star, color: '#d2a14f', action: 'favorite' },
  { label: '我的售后', icon: RefreshLeft, color: '#e8752a', action: 'return' },
  { label: '退出登录', icon: SwitchButton, color: '#a39488', action: 'logout' },
]

function goOrder(status: number) {
  router.push({ path: '/order/list', query: { status } })
}

function onTool(item: Tool) {
  switch (item.action) {
    case 'coupon':
      router.push('/coupon')
      break
    case 'password':
      router.push('/member/change-password')
      break
    case 'address':
      router.push('/member/address')
      break
    case 'favorite':
      router.push('/member/favorite')
      break
    case 'return':
      router.push('/return/list')
      break
    case 'integration':
      router.push('/member/integration')
      break
    case 'logout':
      handleLogout()
      break
  }
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning' })
  } catch {
    return
  }
  userStore.logout()
  // 退出后回首页（不强制进登录页）
  router.push('/product')
}

onMounted(async () => {
  try {
    member.value = await getMemberInfo()
  } catch {
    // 接口失败不影响页面，使用 store 兜底
  }
  try {
    levelInfo.value = await getMemberLevel()
  } catch {
    // 等级信息失败不影响页面其余部分
  }
})
</script>

<style scoped>
.member {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px 16px 48px;
}

/* 用户卡片（暖色生活方式 · 陶土橙） */
.profile {
  position: relative;
  border-radius: var(--mall-radius-lg);
  overflow: hidden;
  margin-bottom: 16px;
  box-shadow: 0 6px 18px rgba(232, 117, 42, 0.18);
}
.profile__bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #e8752a 0%, #f4a45f 100%);
}
.profile__inner {
  position: relative;
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 26px 24px;
  color: #fff;
}
.avatar {
  position: relative;
  width: 68px;
  height: 68px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.22);
  border: 2px solid rgba(255, 255, 255, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 30px;
  font-weight: 800;
  overflow: hidden;
  flex-shrink: 0;
  cursor: pointer;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar__mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.2s;
}
.avatar:hover .avatar__mask,
.avatar--busy .avatar__mask {
  opacity: 1;
}
.avatar__tip {
  font-style: normal;
  font-size: 12px;
}
.avatar--busy {
  pointer-events: none;
}
.profile__info {
  flex: 1;
  min-width: 0;
}
.profile__name {
  font-size: 20px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 10px;
}
.profile__vip {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.25);
}
.profile__phone {
  margin-top: 6px;
  font-size: 14px;
  opacity: 0.92;
}
.profile__meta {
  margin-top: 4px;
  font-size: 12px;
  opacity: 0.8;
}
.profile__setting {
  align-self: flex-start;
  color: #fff;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
  opacity: 0.92;
}
.profile__setting:hover {
  opacity: 1;
}

/* 卡片 */
.card {
  background: var(--mall-card);
  border-radius: var(--mall-radius-lg);
  padding: 18px 20px 22px;
  margin-bottom: 16px;
  box-shadow: var(--mall-shadow);
}
.card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  font-family: var(--mall-font-serif);
  color: var(--mall-text);
}
.card__more {
  font-size: 13px;
  color: var(--mall-text-light);
}
.card__more:hover {
  color: var(--mall-primary);
}

/* 会员成长（债务18：等级 / 成长值 / 积分） */
.growth {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 16px;
}
.growth__item {
  text-align: center;
  padding: 12px 0;
  background: var(--mall-bg);
  border-radius: var(--mall-radius-sm);
}
.growth__num {
  font-size: 18px;
  font-weight: 700;
  color: var(--mall-primary);
  font-variant-numeric: tabular-nums;
}
.growth__label {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-top: 4px;
}
.growth__bar-top {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--mall-text-light);
  margin-bottom: 8px;
}
.growth__bar-top b {
  color: var(--mall-primary);
}
.growth__track {
  height: 8px;
  border-radius: 4px;
  background: var(--mall-primary-soft);
  overflow: hidden;
}
.growth__fill {
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, #e8752a 0%, #f4a45f 100%);
  transition: width 0.4s ease;
}

/* 订单快捷 */
.order-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
}
.order-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 14px 0;
  border-radius: var(--mall-radius-sm);
  cursor: pointer;
  transition: background 0.2s;
}
.order-item:hover {
  background: var(--mall-primary-soft);
}
.order-item__icon {
  color: var(--mall-primary);
}
.order-item__label {
  font-size: 13px;
  color: var(--mall-text);
}

/* 工具宫格 */
.tool-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}
.tool-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 0;
  border-radius: var(--mall-radius-sm);
  cursor: pointer;
  transition: background 0.2s;
}
.tool-item:hover {
  background: var(--mall-bg);
}
.tool-item__label {
  font-size: 13px;
  color: var(--mall-text);
}

@media (max-width: 640px) {
  .order-grid,
  .tool-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .growth {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
