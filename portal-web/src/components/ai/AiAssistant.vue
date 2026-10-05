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
import { ChatDotRound, Close, Delete, Promotion } from '@element-plus/icons-vue'
import AiBubble from './AiBubble.vue'
import { clearChatSession, streamChat } from '@/apis/ai'
import { useLoginGate } from '@/stores/loginGate'
import { useUserStore } from '@/stores/user'
import type { AiConfirm, AiMsg, AiProduct } from '@/types/ai'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const gate = useLoginGate()

const open = ref(false)
const draft = ref('')
const sending = ref(false)
const msgs = ref<AiMsg[]>([])
const confirmState = ref<Record<string, 'pending' | 'confirmed' | 'done' | 'canceled'>>({})
const bodyEl = ref<HTMLElement | null>(null)

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

/** 快捷问题：降低冷启动门槛（都是助手能力覆盖范围内的问题） */
const QUICK = ['找一款降噪耳机', '我购物车里有什么', '帮我推荐一下', '500 元以内有什么好看的杯子']

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
  }
  draft.value = ''

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
    <!-- 悬浮球 -->
    <button v-show="!open" class="ai__fab" type="button" title="购物助手" @click="toggle">
      <el-icon :size="22"><ChatDotRound /></el-icon>
      <span class="ai__fab-tag">助手</span>
    </button>

    <!-- 对话面板 -->
    <transition name="ai-slide">
      <section v-if="open" class="ai__panel">
        <header class="ai__head">
          <span class="ai__avatar">M</span>
          <div class="ai__head-txt">
            <p class="ai__name">小 M · 购物助手</p>
            <p class="ai__sub">帮你找商品、加购物车、下单</p>
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

        <div ref="bodyEl" class="ai__body">
          <!-- 空态 -->
          <div v-if="msgs.length === 0" class="ai__welcome">
            <p class="ai__hello">你好，我是小 M</p>
            <p class="ai__hello-sub">想找点什么？我可以帮您挑商品、加入购物车，也能直接下单。</p>
            <div class="ai__quick">
              <button v-for="q in QUICK" :key="q" type="button" @click="onQuick(q)">{{ q }}</button>
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
          />
        </div>

        <footer class="ai__foot">
          <textarea
            v-model="draft"
            class="ai__input"
            rows="1"
            placeholder="说点什么…（Enter 发送，Shift+Enter 换行）"
            :disabled="sending"
            @keydown.enter.exact.prevent="send()"
          />
          <button v-if="!sending" class="ai__send" type="button" :disabled="!draft.trim()" @click="send()">
            <el-icon :size="16"><Promotion /></el-icon>
          </button>
          <button v-else class="ai__send ai__send--stop" type="button" @click="stop">停止</button>
        </footer>
      </section>
    </transition>
  </div>
</template>

<style scoped>
.ai__fab {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 2000;
  width: 56px;
  height: 56px;
  border: none;
  border-radius: 50%;
  background: var(--mall-primary-gradient);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 22px rgba(192, 116, 79, 0.4);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.ai__fab:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(192, 116, 79, 0.46);
}
.ai__fab-tag {
  position: absolute;
  right: 60px;
  white-space: nowrap;
  font-size: 12px;
  color: var(--mall-primary-dark);
  background: var(--mall-card);
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius-sm);
  padding: 2px 8px;
  box-shadow: var(--mall-shadow);
}

.ai__panel {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 2001;
  width: 384px;
  height: 580px;
  max-height: calc(100vh - 56px);
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
  font-weight: 800;
  font-size: 15px;
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
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 空态 */
.ai__welcome {
  padding: 6px 2px;
}
.ai__hello {
  margin: 0 0 6px;
  font-family: var(--mall-font-serif);
  font-size: 16px;
  font-weight: 700;
  color: var(--mall-text);
}
.ai__hello-sub {
  margin: 0 0 14px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--mall-text-light);
}
.ai__quick {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.ai__quick button {
  font-size: 12px;
  color: var(--mall-text-regular);
  background: var(--mall-card);
  border: 1px solid var(--mall-border);
  border-radius: 999px;
  padding: 6px 12px;
  cursor: pointer;
  transition: color 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}
.ai__quick button:hover {
  color: var(--mall-primary);
  border-color: var(--mall-primary-light);
  background: var(--mall-primary-soft);
}

/* 输入区 */
.ai__foot {
  flex-shrink: 0;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 10px 12px;
  background: var(--mall-card);
  border-top: 1px solid var(--mall-border);
}
.ai__input {
  flex: 1;
  resize: none;
  border: 1px solid var(--mall-border);
  border-radius: var(--mall-radius);
  background: var(--mall-bg);
  padding: 8px 10px;
  font-size: 13px;
  font-family: inherit;
  color: var(--mall-text);
  line-height: 1.5;
  outline: none;
  max-height: 84px;
}
.ai__input:focus {
  border-color: var(--mall-primary-light);
}
.ai__input::placeholder {
  color: #c3b6a8;
}
.ai__send {
  flex-shrink: 0;
  height: 34px;
  min-width: 44px;
  padding: 0 12px;
  border: none;
  border-radius: var(--mall-radius);
  background: var(--mall-primary-gradient);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: filter 0.18s ease;
}
.ai__send:disabled {
  background: #e2d5c9;
  cursor: not-allowed;
}
.ai__send:not(:disabled):hover {
  filter: brightness(1.05);
}
.ai__send--stop {
  background: #fff;
  color: var(--mall-text-regular);
  border: 1px solid var(--mall-border);
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
    right: 16px;
    bottom: 16px;
    width: 50px;
    height: 50px;
  }
  .ai__fab-tag {
    display: none;
  }
  .ai__panel {
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
