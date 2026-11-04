<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import AssistantCard from '@/components/AssistantCard.vue'
import AssistantFormDrawer from '@/components/AssistantFormDrawer.vue'
import AssistantDetailDrawer from '@/components/AssistantDetailDrawer.vue'
import ShareSubmitDialog from '@/components/ShareSubmitDialog.vue'
import ScopePicker from '@/components/ScopePicker.vue'
import CreateOptionDialog from '@/components/CreateOptionDialog.vue'
import ThirdPartyDrawer from '@/components/ThirdPartyDrawer.vue'
import { useUserStore } from '@/stores/user'
import { useApprovalStore } from '@/stores/approval'
import {
  deleteAssistantApi,
  getCategories,
  getDeleteImpact,
  getAssistants,
  summonAssistantApi,
  updateShareScopeApi,
  updateSubscriptionApi
} from '@/api'
import type { CategoryItem, AssistantAction, AssistantCard as AssistantCardType, ListScope } from '@/types/assistant'
import type { ScopePayload } from '@/types/scope'
import { ApiError } from '@/types/api'

const router = useRouter()
const userStore = useUserStore()
const approvalStore = useApprovalStore()

const scope = ref<ListScope>('all')
const categoryId = ref<number | undefined>(undefined)
const keyword = ref('')
const statusFilter = ref<string>('')
const subscribeFilter = ref<string>('')
const page = ref(1)
const pageSize = 12
const total = ref(0)
const list = ref<AssistantCardType[]>([])
const loading = ref(false)
const loadError = ref(false)

const categories = ref<CategoryItem[]>([])
const selectedIds = ref<number[]>([])
const expandedReject = ref<Record<number, boolean>>({})

const createOptionDialog = ref(false)
const createDrawer = ref(false)
const thirdPartyDrawer = ref(false)
const editDrawer = ref(false)
const detailDrawer = ref(false)
const shareDialog = ref(false)
const scopeDialog = ref(false)

const activeAssistantId = ref<number | null>(null)
const shareTargets = ref<AssistantCardType[]>([])
const editingAffectedCount = ref(0)
const scopeTarget = ref<AssistantCardType | null>(null)
const scopePayload = ref<ScopePayload>({ scopeMode: 'RANGE', orgs: [], roles: [], positions: [], users: [] })
const scopeSaving = ref(false)

const SCOPE_TABS: Array<{ key: ListScope; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'mine', label: '我的助理' },
  { key: 'shared', label: '共享助理' }
]

const STATUS_OPTIONS = [
  { value: '', label: '状态：全部' },
  { value: 'unshared', label: '未共享' },
  { value: 'pending', label: '待审批' },
  { value: 'approved', label: '已共享' },
  { value: 'rejected', label: '已拒绝' }
]

const SUB_OPTIONS = [
  { value: 'subscribed', label: '已订阅' },
  { value: 'removed', label: '已移除' }
]

const selectedCards = computed(() =>
  list.value.filter((c) => selectedIds.value.includes(c.assistantId))
)

async function loadCategories(): Promise<void> {
  try {
    const res = await getCategories()
    categories.value = res.list
  } catch {
    ElMessage.error('分类加载失败')
  }
}

async function loadList(): Promise<void> {
  loading.value = true
  loadError.value = false
  try {
    const res = await getAssistants({
      scope: scope.value,
      categoryId: categoryId.value,
      keyword: keyword.value.trim() || undefined,
      statusFilter: scope.value === 'mine' ? statusFilter.value || undefined : undefined,
      subscribeFilter: scope.value === 'shared' ? subscribeFilter.value || undefined : undefined,
      page: page.value,
      pageSize
    })
    list.value = res.list
    total.value = res.total
    selectedIds.value = selectedIds.value.filter((id) => res.list.some((c) => c.assistantId === id))
  } catch {
    loadError.value = true
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadCategories()
  await loadList()
  approvalStore.refreshPendingCount()
})

watch([scope, categoryId, statusFilter, subscribeFilter], () => {
  page.value = 1
  selectedIds.value = []
  loadList()
})

let kwTimer: ReturnType<typeof setTimeout> | null = null
watch(keyword, () => {
  if (kwTimer) clearTimeout(kwTimer)
  kwTimer = setTimeout(() => {
    page.value = 1
    loadList()
  }, 250)
})

watch(
  () => userStore.role,
  () => {
    page.value = 1
    selectedIds.value = []
    loadList()
    approvalStore.refreshPendingCount()
  }
)

function switchScope(next: ListScope): void {
  scope.value = next
  statusFilter.value = ''
  subscribeFilter.value = next === 'shared' ? 'subscribed' : ''
}

function toggleSelect(card: AssistantCardType, value: boolean): void {
  if (value) {
    if (!selectedIds.value.includes(card.assistantId)) selectedIds.value.push(card.assistantId)
  } else {
    selectedIds.value = selectedIds.value.filter((id) => id !== card.assistantId)
  }
}

/* ---------------- 卡片操作 ---------------- */

async function onCardAction(action: AssistantAction | 'detail' | 'toggleReject', card: AssistantCardType): Promise<void> {
  switch (action) {
    case 'detail':
      activeAssistantId.value = card.assistantId
      detailDrawer.value = true
      break
    case 'toggleReject':
      expandedReject.value[card.assistantId] = !expandedReject.value[card.assistantId]
      break
    case 'edit':
      activeAssistantId.value = card.assistantId
      editingAffectedCount.value = card.authorizedCount
      editDrawer.value = true
      break
    case 'delete':
      await handleDelete(card)
      break
    case 'summon':
      await handleSummon(card)
      break
    case 'shareScope':
      await openScope(card)
      break
    case 'remove':
      await handleSubscription(card, 'remove')
      break
    case 'resubscribe':
      await handleSubscription(card, 'resubscribe')
      break
  }
}

async function handleSummon(card: AssistantCardType): Promise<void> {
  try {
    const res = await summonAssistantApi(card.assistantId)
    router.push({ path: '/new-task', query: { assistant: String(res.assistantId), session: res.sessionId } })
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '召唤失败，请稍后重试')
  }
}

async function handleDelete(card: AssistantCardType): Promise<void> {
  try {
    const impact = await getDeleteImpact(card.assistantId)
    const lines = ['删除后不可恢复，是否确认删除？']
    if (impact.authorizedCount > 0) {
      lines.push(`该助理已共享给 ${impact.authorizedCount} 个授权对象，删除后将同时从他们的助理库移除`)
    }
    if (impact.pendingApplyCount > 0) {
      lines.push(`该助理有 ${impact.pendingApplyCount} 条待审批申请，删除后申请将被终止`)
    }
    await ElMessageBox.confirm(lines.join('\n'), `删除「${card.name}」`, {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消'
    })
    await deleteAssistantApi(card.assistantId)
    ElMessage.success('已删除')
    await loadList()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e instanceof ApiError ? e.message : '删除失败，请稍后重试')
  }
}

async function handleSubscription(card: AssistantCardType, action: 'remove' | 'resubscribe'): Promise<void> {
  const text =
    action === 'remove'
      ? `移除后「${card.name}」将从你的助理库隐藏，可随时重新订阅。确认移除？`
      : `重新订阅后「${card.name}」将恢复可见并可召唤，确认？`
  try {
    await ElMessageBox.confirm(text, action === 'remove' ? '移除共享助理' : '重新订阅', {
      type: 'info',
      confirmButtonText: '确认',
      cancelButtonText: '取消'
    })
    await updateSubscriptionApi(card.assistantId, action)
    ElMessage.success(action === 'remove' ? '已移除' : '已重新订阅')
    await loadList()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e instanceof ApiError ? e.message : '操作失败，请稍后重试')
  }
}

async function openScope(card: AssistantCardType): Promise<void> {
  scopeTarget.value = card
  scopePayload.value = { scopeMode: 'RANGE', orgs: [], roles: [], positions: [], users: [] }
  scopeDialog.value = true
  try {
    const { getShareScopeApi } = await import('@/api')
    const res = await getShareScopeApi(card.assistantId)
    if (res.scope) {
      scopePayload.value = {
        scopeMode: res.scope.scopeMode,
        orgs: res.scope.orgs.map((o) => o.id),
        roles: res.scope.roles.map((r) => r.id),
        positions: res.scope.positions.map((p) => p.id),
        users: res.scope.users.map((u) => u.id)
      }
    }
  } catch {
    // 回显失败不阻断，用户可重新选择
  }
}

async function saveScope(): Promise<void> {
  if (!scopeTarget.value) return
  const p = scopePayload.value
  if (p.scopeMode === 'RANGE' && !p.orgs.length && !p.roles.length && !p.positions.length && !p.users.length) {
    ElMessage.warning('请至少选择一个组织或人员')
    return
  }
  scopeSaving.value = true
  try {
    await updateShareScopeApi(scopeTarget.value.assistantId, p)
    ElMessage.success('共享范围已更新')
    scopeDialog.value = false
    await loadList()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '保存失败，请稍后重试')
  } finally {
    scopeSaving.value = false
  }
}

/* ---------------- 批量共享 ---------------- */

function openBatchShare(): void {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选需要共享的助理')
    return
  }
  shareTargets.value = [...selectedCards.value]
  shareDialog.value = true
}

async function onShareSubmitted(): Promise<void> {
  selectedIds.value = []
  await loadList()
  approvalStore.refreshPendingCount()
}

async function onSaved(): Promise<void> {
  await loadList()
}

/** 添加助理：按创建方式分流（手动创建 → 三步向导；已有接入 → 第三方表单） */
function onCreateModeSelect(mode: 'manual' | 'thirdparty'): void {
  if (mode === 'manual') createDrawer.value = true
  else thirdPartyDrawer.value = true
}

function onCategoryCreated(item: CategoryItem): void {
  if (!categories.value.some((c) => c.categoryId === item.categoryId)) {
    categories.value.push(item)
  }
}

const emptyText = computed(() => {
  if (keyword.value.trim()) return '未找到匹配的助理，试试调整关键词'
  if (scope.value === 'mine') return '你还没有创建助理，点击右上角「添加助理」开始'
  if (scope.value === 'shared') {
    return subscribeFilter.value === 'removed' ? '没有已移除的共享助理' : '暂无共享给你的助理'
  }
  return '暂无可用助理'
})
</script>

<template>
  <div class="page-card">
    <div class="page-head">
      <div>
        <div class="page-title">
          助理
          <span class="beta-badge">BETA</span>
        </div>
        <div class="page-subtitle">
          手动创建或接入第三方助理，配置提示词与能力后可共享给团队；已共享的助理支持版本管理与下架。
        </div>
      </div>
      <div class="page-head-actions">
        <el-button v-if="userStore.isAdmin" @click="router.push('/approvals')">
          审批中心
          <el-badge v-if="approvalStore.pendingCount" :value="approvalStore.pendingCount" class="head-badge" />
        </el-button>
        <el-button type="primary" @click="createOptionDialog = true">添加助理</el-button>
      </div>
    </div>

    <div class="scope-bar">
      <div class="seg-group">
        <div
          v-for="t in SCOPE_TABS"
          :key="t.key"
          class="seg"
          :class="{ active: scope === t.key }"
          @click="switchScope(t.key)"
        >
          {{ t.label }}
        </div>
      </div>
      <div class="scope-right">
        <el-input v-model="keyword" placeholder="搜索助理名称或标签" clearable class="scope-search" />
        <el-select
          v-if="scope === 'mine'"
          v-model="statusFilter"
          placeholder="状态：全部"
          class="scope-select"
        >
          <el-option v-for="o in STATUS_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-select
          v-else-if="scope === 'shared'"
          v-model="subscribeFilter"
          placeholder="订阅状态"
          class="scope-select"
        >
          <el-option v-for="o in SUB_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
      </div>
    </div>

    <div class="cat-tabs">
      <div class="cat-tab" :class="{ active: !categoryId }" @click="categoryId = undefined">全部</div>
      <div
        v-for="c in categories"
        :key="c.categoryId"
        class="cat-tab"
        :class="{ active: categoryId === c.categoryId }"
        @click="categoryId = c.categoryId"
      >
        {{ c.name }}
      </div>
    </div>

    <div class="list-meta">
      <span class="meta-text">共 {{ total }} 个助理 · 点击卡片标题查看详情</span>
      <div v-if="scope === 'mine' && selectedIds.length" class="sel-bar">
        已选 <span class="count-num">{{ selectedIds.length }}</span> 个助理
        <el-button type="primary" size="small" @click="openBatchShare">共享</el-button>
        <el-button link size="small" @click="selectedIds = []">清空</el-button>
      </div>
    </div>

    <div v-loading="loading" class="grid-wrap">
      <div v-if="loadError" class="state-block">
        <span>加载失败，点击重试</span>
        <el-button size="small" @click="loadList">重试</el-button>
      </div>
      <template v-else-if="list.length">
        <div class="assistant-grid">
          <AssistantCard
            v-for="card in list"
            :key="card.assistantId"
            :card="card"
            :scope="scope"
            :selectable="scope === 'mine'"
            :selected="selectedIds.includes(card.assistantId)"
            :expanded-reject="!!expandedReject[card.assistantId]"
            @action="onCardAction"
            @update:selected="(v: boolean) => toggleSelect(card, v)"
          />
        </div>
      </template>
      <div v-else-if="!loading" class="state-block">{{ emptyText }}</div>
    </div>

    <div v-if="total > pageSize" class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        background
        @current-change="loadList"
      />
    </div>

    <CreateOptionDialog v-model="createOptionDialog" @select="onCreateModeSelect" />

    <ThirdPartyDrawer v-model="thirdPartyDrawer" @saved="onSaved" />

    <AssistantFormDrawer
      v-model="createDrawer"
      :categories="categories"
      @saved="onSaved"
      @create-category="onCategoryCreated"
    />

    <AssistantFormDrawer
      v-model="editDrawer"
      :categories="categories"
      :assistant-id="activeAssistantId"
      :affected-grant-count="editingAffectedCount"
      @saved="onSaved"
      @create-category="onCategoryCreated"
    />

    <AssistantDetailDrawer v-model="detailDrawer" :assistant-id="activeAssistantId" />

    <ShareSubmitDialog v-model="shareDialog" :assistants="shareTargets" @submitted="onShareSubmitted" />

    <el-dialog
      v-model="scopeDialog"
      :title="`共享范围 · ${scopeTarget?.name ?? ''}`"
      width="760px"
      :close-on-click-modal="false"
    >
      <div class="scope-dialog-body">
        <div class="scope-notice">
          <span class="notice-dot">i</span>
          <span>
            {{ userStore.isAdmin ? '你是公司管理员，修改后立即生效。' : '修改共享范围需提交审批，管理员通过后生效。' }}
          </span>
        </div>
        <div class="scope-dialog-section">共享范围</div>
        <ScopePicker v-model="scopePayload" />
      </div>
      <template #footer>
        <el-button @click="scopeDialog = false">取消</el-button>
        <el-button type="primary" :loading="scopeSaving" @click="saveScope">
          {{ userStore.isAdmin ? '保存并生效' : '提交变更申请' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.head-badge {
  margin-left: 4px;
}

.beta-badge {
  margin-left: 6px;
  padding: 0 5px;
  border-radius: 3px;
  background: #eef4ff;
  color: var(--at-brand);
  font-size: 10px;
  font-weight: 500;
  line-height: 16px;
  vertical-align: middle;
}

.scope-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-bottom: 12px;
}

.seg-group {
  display: inline-flex;
  flex: 0 0 auto;
  padding: 2px;
  background: #f2f3f5;
  border-radius: 6px;
}

.seg {
  padding: 5px 14px;
  border-radius: 4px;
  font-size: 13px;
  color: var(--at-text-sub);
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.15s;
}

.seg.active {
  background: #fff;
  color: var(--at-text);
  font-weight: 500;
  box-shadow: 0 1px 3px rgba(31, 35, 41, 0.08);
}

.scope-right {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.scope-search {
  width: 220px;
  min-width: 160px;
}

.scope-select {
  width: 130px;
}

.cat-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--at-border);
  margin-bottom: 12px;
}

.cat-tab {
  padding: 4px 12px;
  border-radius: 14px;
  font-size: 13px;
  color: var(--at-text-sub);
  cursor: pointer;
  background: #f7f8fa;
}

.cat-tab:hover {
  color: var(--at-brand);
}

.cat-tab.active {
  background: #eef4ff;
  color: var(--at-brand);
  font-weight: 500;
}

.list-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 32px;
  margin-bottom: 8px;
}

.meta-text {
  font-size: 12px;
  color: var(--at-text-weak);
}

.sel-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  background: #eef4ff;
  border-radius: 4px;
  font-size: 12px;
  color: var(--at-text-sub);
}

.count-num {
  color: var(--at-brand);
  font-weight: 600;
}

.grid-wrap {
  min-height: 240px;
}

.assistant-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.pager {
  display: flex;
  justify-content: center;
  padding-top: 20px;
}

.scope-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 64vh;
  overflow-y: auto;
  padding-right: 4px;
}

.scope-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #eef4ff;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: #2563c9;
}

.notice-dot {
  flex: 0 0 14px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--at-brand);
  color: #fff;
  font-size: 10px;
  font-style: italic;
  display: flex;
  align-items: center;
  justify-content: center;
}

.scope-dialog-section {
  font-size: 14px;
  font-weight: 600;
}
</style>
