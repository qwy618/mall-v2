<script setup lang="ts">
/**
 * 智能购物助手入口：右下悬浮球 + 抽屉式对话面板（移动端全屏）。
 *
 * 职责：
 *  - 维护 UI 消息列表（后端 SSE 事件 → parts）
 *  - 复用 userStore.token 与 useLoginGate()（项目既有约定：需登录不硬跳登录页）
 *  - 会话 id 存 localStorage，提供「开启新会话」
 *
 * 注意：这里只管「展示与交互」，金额一律以助手返回值为准，前端不做二次计算。
 */
import { nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, Close, Delete, Promotion } from '@element-plus/icons-vue'
import AiBubble from './AiBubble.vue'
import AssistantBellIcon from './AssistantBellIcon.vue'
import { AI_AVATAR, AI_INTRO, AI_NAME, AI_ROLE } from './persona'
import { clearChatSession, streamChat } from '@/apis/ai'
import { useLoginGate } from '@/stores/loginGate'
import { useUserStore } from '@/stores/user'
import type { AiCitation, AiConfirm, AiMsg, AiProduct } from '@/types/ai'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const gate = useLoginGate()

/**
 * 面板展开态：由父级 App.vue 的导航栏按钮与移动端悬浮球共同驱动，
 * 故提升为 v-model:open（父级未绑定时退化为组件内本地状态，仍可独立工作）。
 */
const open = defineModel<boolean>('open', { default: false })
const draft = ref('')
const sending = ref(false)
const msgs = ref<AiMsg[]>([])
const confirmState = ref<Record<string, 'pending' | 'confirmed' | 'done' | 'canceled'>>({})
const bodyEl = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)

/** 输入框随内容增高（1~4 行），避免长问题在小框里来回滚 */
function autoGrow() {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 92)}px`
}
/** 发送/清空后收回单行高度 */
function resetInput() {
  const el = inputEl.value
  if (el) el.style.height = 'auto'
}

/** 会话 id：持久化，刷新后仍是同一段记忆 */
const SESSION_KEY = 'ai_session_id'
const sessionId = ref<string>(ensureSessionId())

function ensureSessionId(): string {
  let sid = localStorage.getItem(SESSION_KEY)
  if (!sid) {
    sid =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `s${Date.now()}${Math.floor(Math.random() * 1e6)}`
    localStorage.setItem(SESSION_KEY, sid)
  }
  return sid
}

function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

/**
 * 快捷问题池：降低冷启动门槛，每条都落在助手真实具备的能力里。
 * 每次随机抽一批、且优先与上一批不重复 —— 固定一套会让人以为「只会这几句」。
 *
 * 两条硬约束（都踩过）：
 *  ① **必须指向真实存在的商品**：之前写「找一款降噪耳机」「500 元以内的杯子」，
 *     而库里根本没有耳机/杯子类目，点了只会得到「没找到」——建议必须先在工具层验过有货。
 *  ② 分两组：购物车/个性化推荐类会走登录判定，游客点了会被拦。空态卡片是第一印象，
 *     主体给免登录能答的（搜商品/口碑问答），每批只埋 1~2 条需登录的做能力引导。
 * 池内每条都控制在 8 个汉字以内，一行放得下、不会被裁掉半截。
 */
const QUICK_GUEST = [
  '推荐一款手机',
  '华为手机口碑怎么样',
  '小米手机口碑好吗',
  '有什么好的平板',
  '推荐一款轻薄笔记本',
  '笔记本续航怎么样',
  '想买台大屏电视',
  '固态硬盘怎么挑',
  '推荐一件纯色T恤',
  '运动鞋推荐',
  '想给家里换热水器',
  'iPhone 14 怎么样',
]
const QUICK_MEMBER = [
  '我购物车里有什么',
  '帮我推荐一下',
  '猜猜我喜欢什么',
  '购物车一共多少钱',
  '按我的喜好推荐',
  '帮我看看购物车',
]

const quickCards = ref<string[]>([])
const quickChips = ref<string[]>([])
let lastQuick: string[] = []

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

/** 从池里抽 n 条：优先抽上一批没出现过的；池子不够了才允许重复（否则会抽不满） */
function pickFrom(pool: string[], n: number): string[] {
  const fresh = pool.filter((q) => !lastQuick.includes(q))
  return shuffle(fresh.length >= n ? fresh : pool).slice(0, n)
}

/** 换一批建议：空态卡片 3 免登录 + 1 需登录，底部 chips 2 免登录 + 1 需登录 */
function refreshQuick() {
  const guest = pickFrom(QUICK_GUEST, 5)
  const member = pickFrom(QUICK_MEMBER, 2)
  lastQuick = [...guest, ...member]
  quickCards.value = shuffle([guest[0], guest[1], guest[2], member[0]])
  quickChips.value = [guest[3], guest[4], member[1]]
}
refreshQuick()

function toggle() {
  open.value = !open.value
  if (open.value) nextTick(scrollBottom)
}

/** 面板打开且消息变化时，始终滚到底部 */
function scrollBottom() {
  const el = bodyEl.value
  if (el) el.scrollTop = el.scrollHeight
}
watch(
  () => msgs.value.map((m) => m.parts.length + (m.streaming ? 0.5 : 0)).join(','),
  () => nextTick(scrollBottom),
)

/** 每次展开面板都换一批建议：反复打开看到同一套，会显得像写死的假按钮 */
watch(open, (v) => {
  if (v) refreshQuick()
})

/** 追加文本：续到最后一个 text 片段，保证流式增量拼成一段 */
function appendText(msg: AiMsg, text: string) {
  const last = msg.parts[msg.parts.length - 1]
  if (last && last.kind === 'text') last.text += text
  else msg.parts.push({ kind: 'text', text })
}

function handleEvent(msg: AiMsg, type: string, payload: Record<string, unknown>) {
  switch (type) {
    case 'token':
      appendText(msg, String(payload.content ?? ''))
      break
    case 'tool':
      msg.parts.push({ kind: 'tool', name: String(payload.name ?? '') })
      break
    case 'products':
      msg.parts.push({ kind: 'products', items: (payload.items as AiProduct[]) || [] })
      break
    case 'product':
      msg.parts.push({ kind: 'product', item: payload.item as AiProduct })
      break
    case 'cart_added':
      msg.parts.push({
        kind: 'cart',
        data: {
          cartId: payload.cartId as number,
          productName: String(payload.productName ?? ''),
          price: payload.price as number,
          quantity: payload.quantity as number,
        },
      })
      break
    case 'confirm': {
      const data = payload as unknown as AiConfirm
      msg.parts.push({ kind: 'confirm', data })
      confirmState.value[data.draftId] = 'pending'
      break
    }
    case 'order': {
      msg.parts.push({
        kind: 'order',
        data: {
          orderId: payload.orderId as number,
          orderSn: payload.orderSn as string,
          payAmount: payload.payAmount as number,
        },
      })
      // 下单成功：把最近一张「已确认」的卡片落定为已完成
      const confirmed = Object.keys(confirmState.value).filter(
        (k) => confirmState.value[k] === 'confirmed',
      )
      if (confirmed.length) confirmState.value[confirmed[confirmed.length - 1]] = 'done'
      break
    }
    case 'citation':
      // M3.4：口碑/体验类回答的信息来源（商品名 + 星级 + 评价数，可回跳详情）
      msg.parts.push({ kind: 'citation', items: (payload.items as AiCitation[]) || [] })
      break
    case 'error':
      msg.error = true
      appendText(msg, String(payload.message ?? '服务开小差了，请稍后再试'))
      break
    default:
      break
  }
}

let ctrl: AbortController | null = null

/** 发送一条消息；silent=true 时不在界面上显示这条用户输入（用于系统指令） */
async function send(text?: string, opts: { asSystem?: boolean; silent?: boolean } = {}) {
  const content = (text ?? draft.value).trim()
  if (!content || sending.value) return

  if (!opts.silent) {
    msgs.value.push({ id: uid(), role: 'user', parts: [{ kind: 'text', text: content }] })
    // 问完一句就换一批建议：下一轮看到的是别的问题，而不是老四样
    refreshQuick()
  }
  draft.value = ''
  resetInput()

  // 必须是 reactive 对象：push 进数组后，流式回调仍会继续改它（appendText / streaming / error）。
  // 若用普通对象，那些修改发生在**原始对象**上，绕过了响应式代理的依赖通知，
  // 视图会永远停在「空气泡」（本项目实测踩到过）。
  const asst = reactive<AiMsg>({ id: uid(), role: 'assistant', parts: [], streaming: true })
  msgs.value.push(asst)
  sending.value = true
  await nextTick()
  scrollBottom()

  ctrl = new AbortController()
  await streamChat(
    {
      message: content,
      token: userStore.token || null,
      session_id: sessionId.value,
      as_system: opts.asSystem === true,
    },
    {
      onEvent: (type, payload) => {
        if (type === 'need_login') {
          // 未登录：撤掉这条空回复，弹登录引导（不硬跳登录页）
          const i = msgs.value.findIndex((m) => m.id === asst.id)
          if (i >= 0) msgs.value.splice(i, 1)
          gate.require(route.fullPath, '登录后就能帮您加购物车、下单啦')
          return
        }
        handleEvent(asst, type, payload)
      },
      onError: (message) => {
        asst.error = true
        appendText(asst, message)
      },
      onClose: () => {
        asst.streaming = false
        sending.value = false
        ctrl = null
        nextTick(scrollBottom)
      },
    },
    ctrl.signal,
  )
}

function stop() {
  ctrl?.abort()
  sending.value = false
}

function onQuick(q: string) {
  send(q)
}

/** 确认下单：以「系统指令」发给助手（后端按 SystemMessage 处理），LLM 才会调用下单工具 */
function onConfirm(data: AiConfirm) {
  if (confirmState.value[data.draftId] !== 'pending') return
  confirmState.value[data.draftId] = 'confirmed'
  send(`【系统指令】用户已确认下单，draft_id=${data.draftId}`, { asSystem: true, silent: true })
}

function onCancel(data: AiConfirm) {
  confirmState.value[data.draftId] = 'canceled'
}

/** 点击卡片里的商品：关掉面板直达详情页 */
function onPick(item: AiProduct) {
  open.value = false
  router.push({ path: '/product', query: { pid: String(item.id) } })
}

/** 点击引用卡片（M3.4）：同上，关掉面板直达该商品详情 */
function onCite(item: AiCitation) {
  open.value = false
  router.push({ path: '/product', query: { pid: String(item.productId) } })
}

async function clearAll() {
  try {
    await ElMessageBox.confirm('清除后将开启一段全新对话，当前对话内容不再显示。', '开启新会话', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await clearChatSession(sessionId.value)
  } catch {
    // 服务端清不掉也要让用户能继续用：换一个会话 id，旧记忆自然隔离
    localStorage.removeItem(SESSION_KEY)
    sessionId.value = ensureSessionId()
  }
  msgs.value = []
  confirmState.value = {}
  ElMessage.success('已开启新会话')
}

onBeforeUnmount(() => ctrl?.abort())
</script>

<template>
  <div class="ai">
    <!-- 悬浮球：仅移动端显示（桌面端入口在顶部导航栏购物车左侧） -->
    <button v-show="!open" class="ai__fab" type="button" title="购物助手" @click="toggle">
      <AssistantBellIcon :size="24" />
    </button>

    <!-- 对话面板 -->
    <transition name="ai-slide">
      <section v-if="open" class="ai__panel">
        <header class="ai__head">
          <span class="ai__avatar">{{ AI_AVATAR }}</span>
          <div class="ai__head-txt">
            <p class="ai__name">{{ AI_NAME }} · {{ AI_ROLE }}</p>
            <p class="ai__sub">{{ AI_INTRO }}</p>
          </div>
          <div class="ai__head-btns">
            <button type="button" title="开启新会话" @click="clearAll">
              <el-icon :size="15"><Delete /></el-icon>
            </button>
            <button type="button" title="收起" @click="open = false">
              <el-icon :size="15"><Close /></el-icon>
            </button>
          </div>
        </header>

        <div ref="bodyEl" class="ai__body" :class="{ 'ai__body--empty': msgs.length === 0 }">
          <!-- 空态：能力引导页（比「一行欢迎语 + 几个小按钮」更容易知道能问什么） -->
          <div v-if="msgs.length === 0" class="ai__welcome">
            <span class="ai__welcome-avatar">{{ AI_AVATAR }}</span>
            <p class="ai__hello">你好，我是{{ AI_NAME }}</p>
            <p class="ai__hello-sub">帮你挑商品、加入购物车，也能直接下单。<br />试试下面这些：</p>
            <div class="ai__cards">
              <button v-for="q in quickCards" :key="q" class="ai__card" type="button" @click="onQuick(q)">
                <span>{{ q }}</span>
                <el-icon class="ai__card-go" :size="13"><ArrowRight /></el-icon>
              </button>
            </div>
          </div>

          <AiBubble
            v-for="m in msgs"
            :key="m.id"
            :msg="m"
            :confirm-state="confirmState"
            @confirm="onConfirm"
            @cancel="onCancel"
            @pick="onPick"
            @cite="onCite"
          />
        </div>

        <footer class="ai__foot">
          <!-- 快捷问题常驻：有对话后仍能一键追问，不用自己想措辞；每次问完自动换一批 -->
          <div v-if="msgs.length > 0" class="ai__chips">
            <button v-for="q in quickChips" :key="q" type="button" @click="onQuick(q)">{{ q }}</button>
          </div>

          <div class="ai__composer">
            <textarea
              ref="inputEl"
              v-model="draft"
              class="ai__input"
              rows="1"
              placeholder="说点什么…"
              :disabled="sending"
              @input="autoGrow"
              @keydown.enter.exact.prevent="send()"
            />
            <button
              v-if="!sending"
              class="ai__send"
              type="button"
              title="发送"
              :disabled="!draft.trim()"
              @click="send()"
            >
              <el-icon :size="15"><Promotion /></el-icon>
            </button>
            <button v-else class="ai__send ai__send--stop" type="button" @click="stop">停止</button>
          </div>
          <p class="ai__hint">Enter 发送 · Shift + Enter 换行</p>
        </footer>
      </section>
    </transition>
  </div>
</template>

<style scoped>
/* 悬浮球：桌面端入口已移入导航栏（购物车左侧），这里只在移动端兜底 */
.ai__fab {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 2000;
  width: 52px;
  height: 52px;
  border: none;
  border-radius: 50%;
  background: var(--mall-primary-gradient);
  color: #fff;
  cursor: pointer;
  display: none;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 22px rgba(232, 117, 42, 0.4);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.ai__fab:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(232, 117, 42, 0.46);
}

.ai__panel {
  position: fixed;
  right: 28px;
  top: 122px;
  z-index: 2001;
  width: 400px;
  height: min(640px, calc(100vh - 150px));
  display: flex;
  flex-direction: column;
  background: var(--mall-bg);
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-lg);
  overflow: hidden;
  box-shadow: 0 18px 50px rgba(120, 84, 60, 0.26);
}

/* 头部 */
.ai__head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--mall-card);
  border-bottom: 1px solid var(--mall-border);
}
.ai__avatar {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--mall-primary-gradient);
  color: #fff;
  font-family: var(--mall-font-logo);
  font-weight: 800;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ai__head-txt {
  flex: 1;
  min-width: 0;
}
.ai__name {
  margin: 0;
  font-family: var(--mall-font-serif);
  font-size: 14px;
  font-weight: 700;
  color: var(--mall-text);
  letter-spacing: 0.5px;
}
.ai__sub {
  margin: 1px 0 0;
  font-size: 11px;
  color: var(--mall-text-light);
}
.ai__head-btns {
  display: flex;
  gap: 4px;
}
.ai__head-btns button {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--mall-text-light);
  border-radius: var(--mall-radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ai__head-btns button:hover {
  color: var(--mall-primary);
  background: var(--mall-primary-soft);
}

/* 消息区 */
.ai__body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
/* 空态垂直居中：避免「内容贴顶 + 下方一大片空白」。
 * 🔴 用 .ai__welcome 的 margin:auto，不要用容器的 justify-content:center ——
 *    空态内容比容器高时（窄屏 / 矮窗口），justify-content:center 会把顶部的
 *    头像和问候语顶出可视区，且滚不回去（scrollHeight > clientHeight，但上滚没有内容）。
 *    margin:auto 在空间够时居中、不够时自然从顶部开始排，能滚。 */
.ai__body--empty {
  justify-content: flex-start;
}
.ai__body--empty .ai__welcome {
  margin: auto;
}

/* ---------- 空态：能力引导 ---------- */
.ai__welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 0 4px;
}
.ai__welcome-avatar {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: var(--mall-primary-gradient);
  color: #fff;
  font-family: var(--mall-font-logo);
  font-size: 27px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 20px rgba(232, 117, 42, 0.26);
  margin-bottom: 12px;
}
.ai__hello {
  margin: 0 0 6px;
  font-family: var(--mall-font-serif);
  font-size: 17px;
  font-weight: 700;
  color: var(--mall-text);
}
.ai__hello-sub {
  margin: 0 0 18px;
  font-size: 12px;
  line-height: 1.75;
  color: var(--mall-text-light);
}
.ai__cards {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ai__card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  background: var(--mall-card);
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius);
  font-size: 13px;
  font-family: inherit;
  color: var(--mall-text);
  text-align: left;
  cursor: pointer;
  transition: color 0.18s ease, border-color 0.18s ease, background 0.18s ease,
    transform 0.18s ease;
}
.ai__card:hover {
  color: var(--mall-primary-dark);
  border-color: var(--mall-primary-light);
  background: var(--mall-primary-soft);
  transform: translateX(2px);
}
.ai__card-go {
  flex-shrink: 0;
  color: var(--mall-text-light);
}
.ai__card:hover .ai__card-go {
  color: var(--mall-primary);
}

/* ---------- 输入区 ---------- */
.ai__foot {
  flex-shrink: 0;
  padding: 8px 12px 10px;
  background: var(--mall-card);
  border-top: 1px solid var(--mall-border);
}

/*
 * 常驻快捷问题：**换行而不是横向滚动** —— 之前用 overflow-x 隐藏滚动条，
 * 第 4 条只露出半截且没有任何可滑的暗示，看起来就像被裁坏了。
 * 现在每条 ≤8 个汉字 + 收窄内边距，一行正好放下 3 条；万一还是放不下就换行，绝不裁字。
 */
.ai__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-bottom: 8px;
}
.ai__chips button {
  flex: 0 1 auto;
  max-width: 100%;
  white-space: nowrap;
  font-size: 12px;
  font-family: inherit;
  color: var(--mall-text-regular);
  background: var(--mall-bg);
  border: 1px solid var(--mall-border);
  border-radius: 999px;
  padding: 5px 10px;
  cursor: pointer;
  transition: color 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}
.ai__chips button:hover {
  color: var(--mall-primary);
  border-color: var(--mall-primary-light);
  background: var(--mall-primary-soft);
}

/* 一体化输入框：输入与发送同处一个圆角容器，聚焦时整框高亮 */
.ai__composer {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  padding: 5px 5px 5px 12px;
  border: 1px solid var(--mall-border);
  border-radius: 14px;
  background: var(--mall-bg);
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}
.ai__composer:focus-within {
  border-color: var(--mall-primary-light);
  box-shadow: 0 0 0 3px rgba(232, 117, 42, 0.1);
}
.ai__input {
  flex: 1;
  min-width: 0;
  resize: none;
  border: none;
  background: transparent;
  padding: 7px 0;
  font-size: 13px;
  font-family: inherit;
  color: var(--mall-text);
  line-height: 1.55;
  outline: none;
  max-height: 92px;
}
.ai__input::placeholder {
  color: #c3b6a8;
}
.ai__send {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: var(--mall-primary-gradient);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: filter 0.18s ease, background 0.18s ease;
}
.ai__send:disabled {
  background: #e2d5c9;
  cursor: not-allowed;
}
.ai__send:not(:disabled):hover {
  filter: brightness(1.06);
}
.ai__send--stop {
  width: auto;
  min-width: 46px;
  padding: 0 12px;
  border-radius: 999px;
  background: #fff;
  color: var(--mall-text-regular);
  border: 1px solid var(--mall-border);
  font-size: 12px;
}
.ai__send--stop:hover {
  color: var(--mall-primary);
  border-color: var(--mall-primary-light);
  background: var(--mall-primary-soft);
}
.ai__hint {
  margin: 6px 2px 0;
  font-size: 11px;
  color: var(--mall-text-light);
  text-align: right;
}

/* 动画 */
.ai-slide-enter-active,
.ai-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.ai-slide-enter-from,
.ai-slide-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

/* 移动端：全屏面板 */
@media (max-width: 768px) {
  .ai__fab {
    display: flex;
  }
  .ai__panel {
    top: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    height: 100%;
    max-height: 100%;
    border-radius: 0;
    border: none;
  }
}
</style>
