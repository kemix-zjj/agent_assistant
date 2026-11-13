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
import OfflineSubmitDialog from '@/components/OfflineSubmitDialog.vue'
import { useUserStore } from '@/stores/user'
import { useApprovalStore } from '@/stores/approval'
import {
  createCategory,
  deleteAssistantApi,
  deleteCategory,
  getCategories,
  getDeleteImpact,
  getAssistants,
  renameCategory,
  summonAssistantApi,
  updateShareScopeApi,
  updateSubscriptionApi
} from '@/api'
import type {
  CategoryItem,
  AssistantAction,
  AssistantCard as AssistantCardType,
  AssistantDetail,
  ListScope
} from '@/types/assistant'
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

const createOptionDialog = ref(false)
const createDrawer = ref(false)
const thirdPartyDrawer = ref(false)
const editDrawer = ref(false)
const detailDrawer = ref(false)
const shareDialog = ref(false)
const scopeDialog = ref(false)
const categoryDialog = ref(false)
const offlineDialog = ref(false)
const offlineTarget = ref<AssistantCardType | null>(null)
const deleteDialog = ref(false)
const deleteTarget = ref<AssistantCardType | null>(null)
const deleteImpact = ref<{ authorizedCount: number; pendingApplyCount: number } | null>(null)
const deleteSaving = ref(false)

const activeAssistantId = ref<number | null>(null)
const shareTargets = ref<AssistantCardType[]>([])
const shareInitialScope = ref<ScopePayload | null>(null)
const scopeTarget = ref<AssistantCardType | null>(null)
const scopePayload = ref<ScopePayload>({ scopeMode: 'RANGE', orgs: [], roles: [], positions: [], users: [] })
const scopeSaving = ref(false)

/** 分类管理弹窗 */
const newCategoryName = ref('')
const editingCategoryId = ref<number | null>(null)
const editingCategoryName = ref('')
const categorySaving = ref(false)

/** 三个页签：全部 / 我的助理 / 共享助理（授权管理已按需求移除） */
const SCOPE_TABS: Array<{ key: ListScope; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'mine', label: '我的助理' },
  { key: 'shared', label: '共享助理' }
]

/** 状态筛选：审批中聚合四类审批中，已拒绝聚合全部拒绝子类 */
const STATUS_OPTIONS = [
  { value: '', label: '状态：全部' },
  { value: 'unshared', label: '状态：未共享' },
  { value: 'approved', label: '状态：已共享' },
  { value: 'pending', label: '状态：审批中' },
  { value: 'rejected', label: '状态：已拒绝' },
  { value: 'offline', label: '状态：已下架' }
]

const SUB_OPTIONS = [
  { value: '', label: '订阅状态：全部' },
  { value: 'subscribed', label: '状态：已订阅' },
  { value: 'removed', label: '状态：已移除' }
]

const selectedCards = computed(() =>
  list.value.filter((c) => selectedIds.value.includes(c.assistantId))
)

const selectedCount = computed(() => selectedIds.value.length)

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

/** 「全部」范围下按后端透传的角标口径展示，无需再额外拉取被拒绝列表 */
async function refreshAll(): Promise<void> {
  await loadList()
  approvalStore.refreshPendingCount()
}

onMounted(async () => {
  await loadCategories()
  await refreshAll()
})

watch([scope, categoryId, statusFilter, subscribeFilter], () => {
  page.value = 1
  selectedIds.value = []
  refreshAll()
})

let kwTimer: ReturnType<typeof setTimeout> | null = null
watch(keyword, () => {
  if (kwTimer) clearTimeout(kwTimer)
  kwTimer = setTimeout(() => {
    page.value = 1
    refreshAll()
  }, 250)
})

watch(
  () => userStore.role,
  () => {
    page.value = 1
    selectedIds.value = []
    refreshAll()
  }
)

/** 分类被删除后回落「全部」 */
watch(categories, (next) => {
  if (categoryId.value && !next.some((c) => c.categoryId === categoryId.value)) {
    categoryId.value = undefined
  }
})

function switchScope(next: ListScope): void {
  scope.value = next
  statusFilter.value = ''
  subscribeFilter.value = ''
}

function toggleSelect(card: AssistantCardType, value: boolean): void {
  if (value) {
    if (!selectedIds.value.includes(card.assistantId)) selectedIds.value.push(card.assistantId)
  } else {
    selectedIds.value = selectedIds.value.filter((id) => id !== card.assistantId)
  }
}

/* ---------------- 卡片操作 ---------------- */

async function onCardAction(action: AssistantAction | 'detail', card: AssistantCardType): Promise<void> {
  switch (action) {
    case 'detail':
      activeAssistantId.value = card.assistantId
      detailDrawer.value = true
      break
    case 'summon':
      await handleSummon(card)
      break
    case 'shareScope':
      await openScope(card)
      break
    case 'offline':
      openOfflineDialog(card)
      break
    default:
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

/** 详情 → 卡片结构（仅用于复用卡片上的操作逻辑） */
function detailToCard(d: AssistantDetail): AssistantCardType {
  const desc = d.description ?? ''
  return {
    assistantId: d.assistantId,
    name: d.name,
    avatarType: d.avatarType,
    avatarChar: d.avatarChar,
    avatarUrl: d.avatarUrl,
    avatarColor: d.avatarColor,
    categoryId: d.categoryId,
    categoryName: d.categoryName,
    tags: d.tags,
    description: desc,
    descriptionTruncated: desc.length > 60 ? `${desc.slice(0, 60)}…` : desc,
    source: d.source,
    shareStatus: d.shareStatus,
    pendingType: d.pendingType,
    rejectType: d.rejectType,
    subscribeStatus: d.subscribeStatus,
    version: d.version,
    hasShared: d.hasShared,
    ownerName: d.ownerName,
    ownerTitle: d.ownerDeptName,
    sharedFrom: d.source === 'shared' && d.ownerName
      ? { ownerName: d.ownerName, ownerDeptName: d.ownerDeptName ?? '' }
      : null,
    rejectReason: d.rejectReason,
    offlineReason: d.offlineReason,
    lastApproverName: d.lastApproverName,
    lastApproveTime: d.lastApproveTime,
    authorizedCount: d.shareScope?.grantTotal ?? 0,
    createdAt: d.createdAt,
    updatedAt: d.updatedAt,
    actions: []
  }
}

/** 详情抽屉内的操作：编辑 / 删除 / 共享 / 重新提交 / 移除 / 重新订阅
 *  详情响应不含列表卡片字段，这里把详情对象转换成卡片所需的最小结构。
 */
async function onDetailAction(action: AssistantAction, detail: AssistantDetail): Promise<void> {
  detailDrawer.value = false
  const card = detailToCard(detail)
  switch (action) {
    case 'edit':
      activeAssistantId.value = card.assistantId
      editDrawer.value = true
      break
    case 'delete':
      await handleDelete(card)
      break
    case 'share':
      openShareDialog(card, null)
      break
    case 'resubmit':
      // 已下架 → 重新共享；已拒绝 · 授权审批 → 范围授权页；其余已拒绝 → 编辑页重新提交
      if (detail.shareStatus === 'offline') {
        openShareDialog(card, null)
      } else if (detail.rejectType === 'scope') {
        await openScope(card)
      } else {
        activeAssistantId.value = card.assistantId
        editDrawer.value = true
      }
      break
    case 'remove':
      await handleSubscription(card, 'remove')
      break
    case 'resubscribe':
      await handleSubscription(card, 'resubscribe')
      break
    case 'summon':
      await handleSummon(card)
      break
    case 'shareScope':
      await openScope(card)
      break
    case 'offline':
      openOfflineDialog(card)
      break
  }
}

/** 申请下架：打开原因填写弹窗，提交后进入管理员审批 */
function openOfflineDialog(card: AssistantCardType): void {
  offlineTarget.value = card
  offlineDialog.value = true
}

/** 删除确认弹窗（对齐 prototype deleteAssistant：说明 + 橙色影响提示块） */
async function handleDelete(card: AssistantCardType): Promise<void> {
  try {
    deleteImpact.value = await getDeleteImpact(card.assistantId)
    deleteTarget.value = card
    deleteDialog.value = true
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '删除影响面加载失败，请稍后重试')
  }
}

async function confirmDelete(): Promise<void> {
  if (!deleteTarget.value) return
  const card = deleteTarget.value
  deleteSaving.value = true
  try {
    await deleteAssistantApi(card.assistantId)
    ElMessage.success(`已删除「${card.name}」`)
    deleteDialog.value = false
    await refreshAll()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '删除失败，请稍后重试')
  } finally {
    deleteSaving.value = false
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
    await refreshAll()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e instanceof ApiError ? e.message : '操作失败，请稍后重试')
  }
}

/** 首次共享：打开共享申请弹窗（走 POST /shares） */
function openShareDialog(card: AssistantCardType, initial: ScopePayload | null): void {
  shareTargets.value = [card]
  shareInitialScope.value = initial
  shareDialog.value = true
}

function toScopePayload(scopeValue: {
  scopeMode: ScopePayload['scopeMode']
  orgs: Array<{ id: string }>
  roles: Array<{ id: string }>
  positions: Array<{ id: string }>
  users: Array<{ id: string }>
}): ScopePayload {
  return {
    scopeMode: scopeValue.scopeMode,
    orgs: scopeValue.orgs.map((o) => o.id),
    roles: scopeValue.roles.map((r) => r.id),
    positions: scopeValue.positions.map((p) => p.id),
    users: scopeValue.users.map((u) => u.id)
  }
}

/** 已共享助理调整范围：走 PUT /assistants/{id}/share-scope */
async function openScope(card: AssistantCardType): Promise<void> {
  scopeTarget.value = card
  scopePayload.value = { scopeMode: 'RANGE', orgs: [], roles: [], positions: [], users: [] }
  scopeDialog.value = true
  try {
    const { getShareScopeApi } = await import('@/api')
    const res = await getShareScopeApi(card.assistantId)
    if (res.scope) scopePayload.value = toScopePayload(res.scope)
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
    await refreshAll()
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
  shareInitialScope.value = null
  shareDialog.value = true
}

async function onShareSubmitted(): Promise<void> {
  selectedIds.value = []
  await refreshAll()
}

async function onSaved(): Promise<void> {
  await refreshAll()
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

/* ---------------- 分类管理（仅管理员） ---------------- */

function openCategoryDialog(): void {
  newCategoryName.value = ''
  editingCategoryId.value = null
  editingCategoryName.value = ''
  categoryDialog.value = true
}

async function addCategoryItem(): Promise<void> {
  const name = newCategoryName.value.trim()
  if (!name) {
    ElMessage.warning('请输入分类名称')
    return
  }
  if (categories.value.some((c) => c.name === name)) {
    ElMessage.error(`分类「${name}」已存在`)
    return
  }
  categorySaving.value = true
  try {
    const item = await createCategory(name)
    categories.value.push(item)
    newCategoryName.value = ''
    ElMessage.success(`分类「${name}」已新增`)
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '新增分类失败')
  } finally {
    categorySaving.value = false
  }
}

function startRename(item: CategoryItem): void {
  editingCategoryId.value = item.categoryId
  editingCategoryName.value = item.name
}

function cancelRename(): void {
  editingCategoryId.value = null
  editingCategoryName.value = ''
}

async function saveRename(item: CategoryItem): Promise<void> {
  const name = editingCategoryName.value.trim()
  if (!name) {
    ElMessage.warning('请输入分类名称')
    return
  }
  if (name === item.name) {
    cancelRename()
    return
  }
  if (categories.value.some((c) => c.name === name && c.categoryId !== item.categoryId)) {
    ElMessage.error(`分类「${name}」已存在`)
    return
  }
  categorySaving.value = true
  try {
    const updated = await renameCategory(item.categoryId, name)
    const hit = categories.value.find((c) => c.categoryId === item.categoryId)
    if (hit) hit.name = updated.name
    cancelRename()
    ElMessage.success(`分类已重命名为「${updated.name}」`)
    await refreshAll()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '重命名失败')
  } finally {
    categorySaving.value = false
  }
}

async function removeCategory(item: CategoryItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除分类「${item.name}」？删除后不可恢复。`, '删除分类', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    await deleteCategory(item.categoryId)
    categories.value = categories.value.filter((c) => c.categoryId !== item.categoryId)
    if (categoryId.value === item.categoryId) categoryId.value = undefined
    ElMessage.success(`分类「${item.name}」已删除`)
    await refreshAll()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e instanceof ApiError ? e.message : '删除失败，分类下存在助理时不可删除')
  }
}

/* ---------------- 空态文案 ---------------- */

const isEmptyFiltered = computed(
  () => !!keyword.value.trim() || categoryId.value !== undefined || statusFilter.value !== ''
)

const emptyText = computed(() => {
  if (keyword.value.trim()) return '未找到匹配的助理，试试调整关键词'
  if (scope.value === 'mine') {
    if (statusFilter.value) return '没有符合该状态的助理，试试调整筛选条件'
    return '你还没有创建助理，点击右上角「添加助理」开始'
  }
  if (scope.value === 'shared') {
    return subscribeFilter.value === 'removed' ? '没有已移除的共享助理' : '暂无共享给你的助理'
  }
  return isEmptyFiltered.value ? '没有符合条件的助理，试试调整筛选条件' : '暂无可用助理'
})
</script>

<template>
  <div class="page-card at-page">
    <div class="page-head">
      <div class="page-title title-accent">
        助理<span class="beta-badge">BETA</span>
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
      <button v-if="userStore.isAdmin" class="btn-text cat-manage-btn" @click="openCategoryDialog">
        分类管理
      </button>
    </div>

    <div class="list-meta">
      <span class="meta-text">
        <template v-if="scope === 'all'">
          共 {{ total }} 个助理（平台内置 · 已共享 · 已订阅） · 点击卡片查看详情
        </template>
        <template v-else>共 {{ total }} 个助理 · 点击卡片查看详情</template>
      </span>
      <div class="meta-right">
        <div v-if="scope === 'mine' && selectedCount" class="sel-bar">
          已选 <span class="count-num">{{ selectedCount }}</span> 个助理
          <el-button type="primary" size="small" @click="openBatchShare">共享</el-button>
          <el-button link size="small" @click="selectedIds = []">清空</el-button>
        </div>
      </div>
    </div>

    <div v-loading="loading" class="grid-wrap">
      <div v-if="loadError" class="state-block">
        <span>加载失败，点击重试</span>
        <el-button size="small" @click="refreshAll">重试</el-button>
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
        :page-count="Math.ceil(total / pageSize)"
        layout="prev, pager, next"
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
      @saved="onSaved"
      @create-category="onCategoryCreated"
    />

    <AssistantDetailDrawer
      v-model="detailDrawer"
      :assistant-id="activeAssistantId"
      @action="onDetailAction"
    />

    <ShareSubmitDialog
      v-model="shareDialog"
      :assistants="shareTargets"
      :initial-scope="shareInitialScope"
      @submitted="onShareSubmitted"
    />

    <OfflineSubmitDialog
      v-model="offlineDialog"
      :card="offlineTarget"
      @submitted="refreshAll"
    />

    <!-- 删除确认：对齐 prototype deleteAssistant 的文案与影响提示 -->
    <el-dialog
      v-model="deleteDialog"
      title="确认删除该助理？"
      width="460px"
      :close-on-click-modal="false"
    >
      <div class="confirm-body">
        <div class="confirm-text">删除后该助理将从你的助理库中永久移除，且不可恢复。</div>
        <div class="confirm-impact">
          <template v-if="deleteImpact && deleteImpact.pendingApplyCount > 0">
            该助理存在待审批的共享申请，删除后申请将被终止。
          </template>
          <template v-else>当前助理尚未共享，删除仅影响你自己。</template>
        </div>
      </div>
      <template #footer>
        <el-button @click="deleteDialog = false">取消</el-button>
        <el-button type="danger" :loading="deleteSaving" @click="confirmDelete">确认删除</el-button>
      </template>
    </el-dialog>

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

    <el-dialog v-model="categoryDialog" title="分类管理" width="520px">
      <div class="cat-mgr-body">
        <div class="cat-mgr-add">
          <el-input v-model="newCategoryName" placeholder="输入新分类名称" maxlength="10" />
          <el-button type="primary" :loading="categorySaving" @click="addCategoryItem">新增分类</el-button>
        </div>
        <div class="cat-mgr-list">
          <div v-for="c in categories" :key="c.categoryId" class="cat-mgr-row">
            <template v-if="editingCategoryId === c.categoryId">
              <el-input v-model="editingCategoryName" maxlength="10" class="cat-rename-input" />
              <span class="cat-mgr-ops">
                <el-button type="primary" size="small" :loading="categorySaving" @click="saveRename(c)">保存</el-button>
                <el-button size="small" @click="cancelRename">取消</el-button>
              </span>
            </template>
            <template v-else>
              <span class="cat-mgr-name">{{ c.name }}</span>
              <span class="cat-mgr-ops">
                <el-button link type="primary" size="small" @click="startRename(c)">重命名</el-button>
                <el-button link type="danger" size="small" @click="removeCategory(c)">删除</el-button>
              </span>
            </template>
          </div>
        </div>
        <div class="cat-mgr-hint">
          删除前将校验分类下是否存在助理，存在助理的分类不可删除；重命名将同步更新该分类下全部助理。调整后立即生效于筛选页签与创建表单。
        </div>
      </div>
      <template #footer>
        <el-button @click="categoryDialog = false">关闭</el-button>
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

.title-accent {
  position: relative;
  display: inline-block;
  padding-bottom: 6px;
}

.title-accent::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: 0;
  width: 100%;
  height: 3px;
  background: var(--at-text);
  border-radius: 2px;
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
  align-items: center;
  gap: 6px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--at-border);
  margin-bottom: 12px;
}

.cat-tab {
  padding: 5px 16px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--at-text-sub);
  cursor: pointer;
  background: #fff;
  border: 1px solid var(--at-border);
  transition: all 0.15s;
}

.cat-tab:hover {
  color: var(--at-brand);
  border-color: var(--at-brand);
}

.cat-tab.active {
  background: var(--at-brand);
  border-color: var(--at-brand);
  color: #fff;
  font-weight: 500;
}

.cat-manage-btn {
  margin-left: auto;
  padding: 0 6px;
  border: none;
  background: none;
  color: var(--at-text-sub);
  font-size: 13px;
  cursor: pointer;
}

.cat-manage-btn:hover {
  color: var(--at-brand);
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

.meta-right {
  display: flex;
  align-items: center;
  gap: 8px;
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
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

/* 栅格降列：对齐原型断点（1240 → 3 列，920 → 2 列，640 → 1 列） */
@media (max-width: 1240px) {
  .assistant-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 920px) {
  .assistant-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .assistant-grid {
    grid-template-columns: 1fr;
  }
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

/* ---------- 删除确认弹窗（对齐 prototype .confirm-text / .confirm-impact） ---------- */
.confirm-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.confirm-text {
  font-size: 13px;
  line-height: 1.7;
  color: var(--at-text-sub);
}

.confirm-impact {
  padding: 8px 12px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--at-text);
  background: #fff7e8;
  border-radius: 4px;
}

/* ---------- 分类管理 ---------- */
.cat-mgr-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cat-mgr-add {
  display: flex;
  gap: 8px;
}

.cat-mgr-list {
  display: flex;
  flex-direction: column;
  max-height: 320px;
  overflow-y: auto;
}

.cat-mgr-row {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 4px;
  border-bottom: 1px solid #f2f3f5;
}

.cat-mgr-name {
  font-size: 13px;
  font-weight: 600;
}

.cat-mgr-ops {
  margin-left: auto;
  display: flex;
  gap: 4px;
}

.cat-rename-input {
  width: 160px;
}

.cat-mgr-hint {
  font-size: 12px;
  line-height: 1.6;
  color: var(--at-text-weak);
}
</style>
