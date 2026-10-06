<template>
  <div class="page">
    <div class="crumb">
      <span class="link" @click="router.push('/member')">个人中心</span>
      <span class="sep">/</span>
      <span>积分明细</span>
    </div>
    <h2 class="page-title">积分明细</h2>

    <div v-if="level" class="summary">
      <div class="summary__item">
        <div class="summary__num">{{ level.integration }}</div>
        <div class="summary__label">可用积分</div>
      </div>
      <div class="summary__item">
        <div class="summary__num">{{ level.historyIntegration }}</div>
        <div class="summary__label">累计获得</div>
      </div>
      <div class="summary__item">
        <div class="summary__num summary__num--lv">{{ level.levelName }}</div>
        <div class="summary__label">当前等级</div>
      </div>
      <div class="summary__tip">100 积分 = 1 元，下单提交时可抵扣应付金额</div>
    </div>

    <div class="box">
      <div v-loading="loading" class="list">
        <div v-for="h in list" :key="h.id" class="row">
          <div class="row__main">
            <div class="row__type">
              {{ INTEGRATION_CHANGE_TEXT[h.changeType] ?? '积分变动' }}
              <span v-if="h.orderSn" class="row__sn">{{ h.orderSn }}</span>
            </div>
            <div class="row__note">{{ h.operateNote || '—' }}</div>
            <div class="row__time">{{ fmtTime(h.createTime) }}</div>
          </div>
          <div class="row__right">
            <div class="row__delta" :class="h.changeCount >= 0 ? 'is-earn' : 'is-spend'">
              {{ h.changeCount >= 0 ? '+' : '' }}{{ h.changeCount }}
            </div>
            <div class="row__after">余额 {{ h.integrationAfter ?? 0 }}</div>
          </div>
        </div>
        <el-empty
          v-if="!loading && list.length === 0"
          description="还没有积分记录，完成订单即可获得积分"
        />
      </div>
      <el-pagination
        v-if="total > pageSize"
        class="pager"
        background
        layout="prev, pager, next, total"
        :total="total"
        :current-page="pageNum"
        :page-size="pageSize"
        @current-change="onPage"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMemberLevel, listIntegrationHistory } from '@/apis/member'
import { INTEGRATION_CHANGE_TEXT } from '@/types/member'
import type { IntegrationHistory, MemberLevelVO } from '@/types/member'

const router = useRouter()

const level = ref<MemberLevelVO | null>(null)
const list = ref<IntegrationHistory[]>([])
const loading = ref(false)
const pageNum = ref(1)
const pageSize = ref(10)
const total = ref(0)

function fmtTime(t?: string) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}

async function fetchList() {
  loading.value = true
  try {
    const data = await listIntegrationHistory(pageNum.value, pageSize.value)
    list.value = data.list
    total.value = data.total
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  pageNum.value = p
  fetchList()
}

onMounted(async () => {
  try {
    level.value = await getMemberLevel()
  } catch {
    // 汇总失败不影响流水展示
  }
  await fetchList()
})
</script>

<style scoped>
.page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px 16px 48px;
  background: var(--mall-bg);
  min-height: calc(100vh - 60px);
}
.crumb {
  font-size: 13px;
  color: var(--mall-text-light);
  margin-bottom: 12px;
}
.crumb .link {
  cursor: pointer;
  color: var(--mall-primary);
}
.crumb .sep {
  margin: 0 6px;
}
.page-title {
  margin: 0 0 16px;
}
.summary {
  position: relative;
  display: flex;
  align-items: center;
  gap: 40px;
  background: linear-gradient(135deg, #e8752a 0%, #f4a45f 100%);
  border-radius: var(--mall-radius-lg);
  padding: 22px 26px;
  margin-bottom: 16px;
  color: #fff;
  box-shadow: 0 6px 18px rgba(232, 117, 42, 0.18);
}
.summary__item {
  text-align: center;
}
.summary__num {
  font-size: 26px;
  font-weight: 800;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}
.summary__num--lv {
  font-size: 20px;
}
.summary__label {
  font-size: 12px;
  opacity: 0.9;
  margin-top: 4px;
}
.summary__tip {
  margin-left: auto;
  font-size: 12px;
  opacity: 0.92;
}
.box {
  background: var(--mall-card);
  border-radius: var(--mall-radius-lg);
  padding: 8px 20px 18px;
  box-shadow: var(--mall-shadow);
}
.list {
  min-height: 120px;
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 0;
  border-bottom: 1px dashed var(--mall-border);
}
.row:last-of-type {
  border-bottom: none;
}
.row__type {
  font-size: 15px;
  font-weight: 600;
  color: var(--mall-text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.row__sn {
  font-size: 12px;
  font-weight: 400;
  color: var(--mall-text-light);
}
.row__note {
  font-size: 13px;
  color: var(--mall-text);
  margin-top: 4px;
}
.row__time {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-top: 4px;
}
.row__right {
  text-align: right;
  flex: 0 0 auto;
}
.row__delta {
  font-size: 19px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.row__delta.is-earn {
  color: var(--mall-price);
}
.row__delta.is-spend {
  color: #7a9c6b;
}
.row__after {
  font-size: 12px;
  color: var(--mall-text-light);
  margin-top: 4px;
}
.pager {
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
