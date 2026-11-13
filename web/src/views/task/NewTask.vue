<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AssistantAvatar from '@/components/AssistantAvatar.vue'
import { getAssistantDetail, getAssistants, summonAssistantApi } from '@/api'
import type { AssistantCard, AssistantDetail } from '@/types/assistant'

/** 新建任务页：召唤后的对话入口（F-EXP-003） */
const route = useRoute()
const router = useRouter()

interface Message {
  me: boolean
  text: string
}

const current = ref<(AssistantDetail & { categoryName?: string }) | null>(null)
const messages = ref<Message[]>([])
const input = ref('')
const pickerOpen = ref(false)
const pickerKeyword = ref('')
const candidates = ref<AssistantCard[]>([])

const bodyRef = ref<HTMLElement>()

const suggestions = computed(() => {
  if (current.value?.quickQuestions?.length) return current.value.quickQuestions
  return ['帮我梳理这个问题的处理路径', '按制度给出依据与条款', '输出一份可执行的清单']
})

const grouped = computed(() => {
  const kw = pickerKeyword.value.trim()
  const list = kw
    ? candidates.value.filter((c) => c.name.includes(kw) || c.tags.some((t) => t.includes(kw)))
    : candidates.value
  return [
    { title: '我的助理', items: list.filter((c) => c.source === 'custom') },
    { title: '共享助理', items: list.filter((c) => c.source === 'shared') },
    { title: '平台内置', items: list.filter((c) => c.source === 'platform') }
  ].filter((g) => g.items.length)
})

/** createSession=false 表示会话已由入口创建（如列表页召唤），此处只加载助理详情，避免重复召唤 */
async function selectAssistant(assistantId: number, createSession = true): Promise<void> {
  try {
    const detail = await getAssistantDetail(assistantId)
    const session = createSession ? (await summonAssistantApi(assistantId, 'picker')).sessionId : String(route.query.session ?? '')
    current.value = detail
    messages.value = []
    pickerOpen.value = false
    router.replace({ path: '/new-task', query: { assistant: String(assistantId), session } })
  } catch {
    ElMessage.error('助理加载失败，请稍后重试')
  }
}

async function loadCandidates(): Promise<void> {
  try {
    const res = await getAssistants({ scope: 'all', page: 1, pageSize: 50 })
    candidates.value = res.list
  } catch {
    candidates.value = []
  }
}

onMounted(async () => {
  await loadCandidates()
  const q = route.query.assistant
  if (q) {
    // 带 session 说明入口（列表页召唤 / 页面刷新）已建过会话，不再重复召唤
    await selectAssistant(Number(q), !route.query.session)
  }
})

function scrollToBottom(): void {
  nextTick(() => {
    if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
  })
}

function send(): void {
  const text = input.value.trim()
  if (!current.value) {
    ElMessage.warning('请先在 ＋ 中选择一位助理')
    pickerOpen.value = true
    return
  }
  if (!text) return
  messages.value.push({ me: true, text })
  input.value = ''
  scrollToBottom()

  setTimeout(() => {
    const name = current.value?.name ?? '助理'
    messages.value.push({
      me: false,
      text: `（演示回复）已收到你的问题：「${text}」。\n我将按「${name}」的配置处理：先检索关联知识库，再结合技能与连接器给出结论与依据。\n涉及制度条款会附来源；无法确认的问题会提示「需人工确认」。`
    })
    scrollToBottom()
  }, 600)
}

function onKeydown(e: Event | KeyboardEvent): void {
  const evt = e as KeyboardEvent
  if (evt.key === 'Enter' && !evt.shiftKey) {
    e.preventDefault()
    send()
  }
}

function clearAssistant(): void {
  current.value = null
  messages.value = []
  router.replace({ path: '/new-task' })
}

function useSuggestion(text: string): void {
  input.value = text
}
</script>

<template>
  <div class="nt-wrap">
    <div class="nt-head">
      <div>
        <div class="page-title">新建任务</div>
        <div class="page-subtitle">先选择一位助理，再描述你的问题；助理会按提示词、技能与知识库作答。</div>
      </div>
      <el-button @click="router.push('/assistants')">助理列表</el-button>
    </div>

    <div ref="bodyRef" class="nt-body">
      <div v-if="!messages.length" class="nt-hero">
        <AssistantAvatar
          v-if="current"
          :type="current.avatarType"
          :char="current.avatarChar"
          :url="current.avatarUrl"
          :color="current.avatarColor"
          :name="current.name"
          :size="56"
        />
        <div v-else class="hero-placeholder">助</div>
        <div class="hero-title">
          {{ current ? `你好，我是${current.name}` : '选择助理，开始一个新任务' }}
        </div>
        <div class="hero-sub">
          {{ current ? current.description : '点击输入框左侧的 ＋ 选择一位助理，也可以用「助理列表」里的召唤直接开始。' }}
        </div>
        <div class="hero-sugs">
          <button v-for="s in suggestions" :key="s" class="sug" @click="useSuggestion(s)">{{ s }}</button>
        </div>
      </div>

      <div v-else class="nt-msgs">
        <div v-for="(m, i) in messages" :key="i" class="msg" :class="{ me: m.me }">
          <span v-if="m.me" class="msg-avatar me-avatar">我</span>
          <AssistantAvatar
            v-else-if="current"
            :type="current.avatarType"
            :char="current.avatarChar"
            :url="current.avatarUrl"
            :color="current.avatarColor"
            :name="current.name"
            :size="28"
          />
          <div class="bubble">{{ m.text }}</div>
        </div>
      </div>
    </div>

    <div class="nt-composer">
      <div class="nt-card">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="给助理发送消息，Enter 发送 / Shift + Enter 换行"
          class="nt-input"
          @keydown="onKeydown"
        />
        <div class="nt-bar">
          <div class="nt-bar-left">
            <button class="nt-plus" title="选择助理" @click="pickerOpen = !pickerOpen">＋</button>
            <div v-if="current" class="nt-select">
              <AssistantAvatar
                :type="current.avatarType"
                :char="current.avatarChar"
                :url="current.avatarUrl"
                :color="current.avatarColor"
                :name="current.name"
                :size="20"
              />
              <span class="nt-select-name">{{ current.name }}</span>
              <span class="nt-select-ver">{{ current.version }}</span>
              <span class="nt-select-x" @click="clearAssistant">×</span>
            </div>
            <span v-else class="nt-select-empty">未选择助理 · 点击左侧 ＋ 选择</span>

            <div v-if="pickerOpen" class="nt-picker">
              <el-input v-model="pickerKeyword" size="small" placeholder="搜索助理名称或标签" clearable />
              <div class="picker-list">
                <template v-if="grouped.length">
                  <template v-for="g in grouped" :key="g.title">
                    <div class="picker-group">{{ g.title }}</div>
                    <div
                      v-for="c in g.items"
                      :key="c.assistantId"
                      class="picker-item"
                      :class="{ active: current?.assistantId === c.assistantId }"
                      @click="selectAssistant(c.assistantId)"
                    >
                      <AssistantAvatar
                        :type="c.avatarType"
                        :char="c.avatarChar"
                        :url="c.avatarUrl"
                        :color="c.avatarColor"
                        :name="c.name"
                        :size="22"
                      />
                      <span class="picker-name">{{ c.name }}</span>
                      <span class="picker-meta">
                        {{ c.source === 'platform' ? '平台内置' : c.source === 'shared' ? `共享自 ${c.sharedFrom?.ownerName ?? ''}` : '我的助理' }}
                      </span>
                    </div>
                  </template>
                </template>
                <div v-else class="picker-empty">没有匹配的助理</div>
              </div>
              <div class="picker-foot" @click="router.push('/assistants')">＋ 去助理列表添加助理</div>
            </div>
          </div>
          <el-button type="primary" @click="send">发送</el-button>
        </div>
      </div>
      <div class="nt-tip">当前为演示数据：回复为模拟内容；切换助理会开启新的任务。</div>
    </div>
  </div>
</template>

<style scoped>
.nt-wrap {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 32px);
  background: #fff;
  border-radius: var(--at-radius);
  padding: 20px;
}

.nt-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.nt-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.nt-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 56px 0 24px;
  text-align: center;
}

.hero-placeholder {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: #dde6f2;
  color: #8fa3bf;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}

.hero-title {
  margin-top: 16px;
  font-size: 17px;
  font-weight: 600;
}

.hero-sub {
  margin-top: 8px;
  max-width: 560px;
  font-size: 13px;
  line-height: 21px;
  color: var(--at-text-sub);
}

.hero-sugs {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 20px;
}

.sug {
  padding: 6px 12px;
  border: 1px solid var(--at-border);
  border-radius: 16px;
  background: #fff;
  color: var(--at-text-sub);
  font-size: 12px;
  cursor: pointer;
}

.sug:hover {
  border-color: var(--at-brand);
  color: var(--at-brand);
}

.nt-msgs {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 8px 4px;
}

.msg {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.msg.me {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  border-radius: 10px;
  background: #7c8493;
  color: #fff;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bubble {
  max-width: 70%;
  padding: 9px 12px;
  background: #f5f6f7;
  border-radius: 8px;
  font-size: 13px;
  line-height: 21px;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg.me .bubble {
  background: #eef4ff;
}

.nt-composer {
  padding-top: 12px;
}

.nt-card {
  border: 1px solid var(--at-border);
  border-radius: 8px;
  padding: 8px 12px 10px;
}

.nt-input :deep(.el-textarea__inner) {
  box-shadow: none;
  padding: 4px 0;
  font-size: 13px;
}

.nt-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}

.nt-bar-left {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.nt-plus {
  width: 26px;
  height: 26px;
  border: 1px solid var(--at-border);
  border-radius: 6px;
  background: #fff;
  color: var(--at-text-sub);
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
}

.nt-plus:hover {
  border-color: var(--at-brand);
  color: var(--at-brand);
}

.nt-select {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  background: #f2f3f5;
  border-radius: 6px;
  font-size: 12px;
}

.nt-select-name {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nt-select-ver {
  color: var(--at-text-weak);
  font-size: 11px;
}

.nt-select-x {
  cursor: pointer;
  color: var(--at-text-weak);
  padding: 0 2px;
}

.nt-select-x:hover {
  color: var(--at-text);
}

.nt-select-empty {
  font-size: 12px;
  color: var(--at-text-weak);
}

.nt-picker {
  position: absolute;
  bottom: 34px;
  left: 0;
  width: 360px;
  background: #fff;
  border: 1px solid var(--at-border);
  border-radius: 8px;
  box-shadow: 0 6px 24px rgba(31, 35, 41, 0.12);
  padding: 10px;
  z-index: 20;
}

.picker-list {
  max-height: 260px;
  overflow-y: auto;
  margin-top: 8px;
}

.picker-group {
  padding: 4px 6px;
  font-size: 11px;
  color: var(--at-text-weak);
}

.picker-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
}

.picker-item:hover,
.picker-item.active {
  background: #eef4ff;
}

.picker-name {
  font-size: 13px;
}

.picker-meta {
  margin-left: auto;
  font-size: 11px;
  color: var(--at-text-weak);
}

.picker-empty {
  padding: 24px 0;
  text-align: center;
  font-size: 12px;
  color: var(--at-text-weak);
}

.picker-foot {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--at-border);
  font-size: 12px;
  color: var(--at-brand);
  cursor: pointer;
}

.nt-tip {
  margin-top: 8px;
  text-align: center;
  font-size: 11px;
  color: var(--at-text-weak);
}
</style>
