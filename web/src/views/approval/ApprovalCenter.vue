<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AssistantAvatar from '@/components/AssistantAvatar.vue'
import ScopePicker from '@/components/ScopePicker.vue'
import { useUserStore } from '@/stores/user'
import { useApprovalStore } from '@/stores/approval'
import {
  adjustApprovalScope,
  approveApproval,
  getApprovalDetail,
  getApprovals,
  rejectApproval
} from '@/api'
import type { ApprovalCard, ApprovalDetail } from '@/types/approval'
import type { Scope, ScopePayload, ScopeMode } from '@/types/scope'
import { ApiError } from '@/types/api'

/**
 * 审批中心（对齐 prototype D-AT-APPR）
 * - 行式列表 / 卡片双视图，右上角胶囊分段切换
 * - 详情抽屉 760px：元信息行 → 助理信息 → 能力组成 → 变更说明 → 授权范围
 * - 底部：稍后处理 / 审批拒绝 / 审批通过；通过前确认，拒绝需填原因
 */
const router = useRouter()
const userStore = useUserStore()
const approvalStore = useApprovalStore()

const view = ref<'list' | 'card'>('list')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const list = ref<ApprovalCard[]>([])
const loading = ref(false)
const loadError = ref(false)

const detailOpen = ref(false)
const detail = ref<ApprovalDetail | null>(null)
const detailLoading = ref(false)
const adjusting = ref(false)
const scopePayload = ref<ScopePayload>({ scopeMode: 'RANGE', orgs: [], roles: [], positions: [], users: [] })
const deciding = ref(false)

/** 确认弹窗（对齐原型 confirmDialog） */
const confirmOpen = ref(false)
const confirmTitle = ref('')
const confirmText = ref('')
const confirmImpact = ref('')
const confirmAction = ref<'approve' | 'reject'>('approve')

/** 拒绝弹窗 */
const rejectOpen = ref(false)
const rejectReason = ref('')

const TYPE_TEXT: Record<string, { color: string; label: string }> = {
  share: { color: 'blue', label: '共享申请' },
  scope_change: { color: 'default', label: '范围变更' },
  offline: { color: 'warning', label: '下架申请' }
}

const currentActionable = computed(() => detail.value?.status === 'pending')
const isOfflineType = computed(() => detail.value?.approvalType === 'offline')
const isScopeChangeType = computed(() => detail.value?.approvalType === 'scope_change')

const submitterLine = computed(() => {
  const d = detail.value
  if (!d) return ''
  const typeName = TYPE_TEXT[d.approvalType]?.label ?? d.approvalType
  const dept = d.submitterDept ? `（${d.submitterDept}）` : ''
  return `${typeName} · 单号：${d.approvalNo} · 提交人：${d.submitterName}${dept} · ${d.submitTime}`
})

async function loadList(): Promise<void> {
  if (!userStore.isAdmin) {
    loadError.value = false
    list.value = []
    total.value = 0
    return
  }
  loading.value = true
  loadError.value = false
  try {
    const res = await getApprovals({ status: 'pending', page: page.value, pageSize })
    list.value = res.list
    total.value = res.total
  } catch {
    loadError.value = true
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadList()
  approvalStore.refreshPendingCount()
})

function typeLabel(t: string): string {
  return TYPE_TEXT[t]?.label ?? t
}

/** 列表副标题：下架申请展示原因，范围变更展示「变更授权范围」，共享申请展示授权范围 */
function rowSubtitle(card: ApprovalCard): string {
  if (card.approvalType === 'offline') return `下架原因：${card.changeNote || ''}`
  if (card.approvalType === 'scope_change') return card.changeNote || '变更授权范围'
  return `授权范围：${card.scopeSummary || '未设置'}`
}

function tagType(t: string): 'primary' | 'warning' | 'info' {
  if (t === 'offline') return 'warning'
  if (t === 'scope_change') return 'info'
  return 'primary'
}

async function openDetail(approvalId: number): Promise<void> {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = null
  adjusting.value = false
  rejectReason.value = ''
  try {
    const d = await getApprovalDetail(approvalId)
    detail.value = d
    scopePayload.value = d.scope
      ? {
          scopeMode: d.scope.scopeMode as ScopeMode,
          orgs: d.scope.orgs.map((o) => o.id),
          roles: d.scope.roles.map((r) => r.id),
          positions: d.scope.positions.map((p) => p.id),
          users: d.scope.users.map((u) => u.id)
        }
      : { scopeMode: 'RANGE', orgs: [], roles: [], positions: [], users: [] }
  } catch (e) {
    if (e instanceof ApiError && e.code === 'APPROVAL_ALREADY_HANDLED') {
      ElMessage.warning('该申请已被处理，列表已刷新')
      detailOpen.value = false
      await afterDecision()
    } else {
      ElMessage.error(e instanceof ApiError ? e.message : '审批详情加载失败')
      detailOpen.value = false
    }
  } finally {
    detailLoading.value = false
  }
}

async function saveAdjust(): Promise<void> {
  if (!detail.value) return
  const p = scopePayload.value
  if (p.scopeMode === 'RANGE' && !p.orgs.length && !p.roles.length && !p.positions.length && !p.users.length) {
    ElMessage.warning('授权范围不可为空，请至少保留 1 名人员')
    return
  }
  try {
    const res = await adjustApprovalScope(detail.value.approvalId, p)
    detail.value.scope = res.scope
    detail.value.scopeDiff = res.scopeDiff
    detail.value.scopeAdjusted = true
    adjusting.value = false
    ElMessage.success('授权范围已调整，将在审批通过时生效')
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '范围调整失败')
  }
}

/** 通过前的确认弹窗文案：按申请类型区分 */
function askApprove(): void {
  const d = detail.value
  if (!d) return
  confirmAction.value = 'approve'
  confirmTitle.value = '确认审批通过？'
  if (d.approvalType === 'offline') {
    confirmText.value = '通过后该助理将立即下架，并从所有授权对象的助理库中移除。'
    confirmImpact.value = `助理：${d.assistant.name}`
  } else if (d.approvalType === 'scope_change') {
    confirmText.value = '通过后新的授权范围立即生效。'
    confirmImpact.value = `最终授权对象：${d.scope?.grantTotal ?? 0} 人 · ${d.scope?.summary ?? ''}`
  } else {
    confirmText.value = '通过后该助理将出现在授权对象的助理库中，并标识「共享」。'
    confirmImpact.value =
      `最终授权对象：${d.scope?.grantTotal ?? 0} 人 · ${d.scope?.summary ?? ''}` +
      (d.scopeAdjusted ? '（已按管理员调整结果生效）' : '')
  }
  confirmOpen.value = true
}

function askReject(): void {
  rejectReason.value = ''
  confirmAction.value = 'reject'
  rejectOpen.value = true
}

async function confirmApprove(): Promise<void> {
  if (!detail.value) return
  deciding.value = true
  try {
    await approveApproval(detail.value.approvalId)
    ElMessage.success('已审批通过')
    confirmOpen.value = false
    detailOpen.value = false
    await afterDecision()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '审批失败，请稍后重试')
  } finally {
    deciding.value = false
  }
}

async function confirmReject(): Promise<void> {
  if (!detail.value) return
  const reason = rejectReason.value.trim()
  if (!reason) {
    ElMessage.error('请填写拒绝原因')
    return
  }
  deciding.value = true
  try {
    await rejectApproval(detail.value.approvalId, reason)
    ElMessage.success(detail.value.approvalType === 'offline' ? '已拒绝该下架申请' : '已拒绝该申请')
    rejectOpen.value = false
    detailOpen.value = false
    await afterDecision()
  } catch (e) {
    if (e instanceof ApiError && e.code === 'REJECT_REASON_REQUIRED') {
      ElMessage.error('请填写拒绝原因')
    } else {
      ElMessage.error(e instanceof ApiError ? e.message : '审批失败，请稍后重试')
    }
  } finally {
    deciding.value = false
  }
}

async function afterDecision(): Promise<void> {
  await loadList()
  await approvalStore.refreshPendingCount()
}

/** 授权对象统计：人员 N（组织 X · 单独添加 Y） */
function scopePeopleLine(scope: Scope | null): string {
  if (!scope) return ''
  if (scope.scopeMode === 'PUBLIC') return '公开 · 全公司可用'
  const direct = scope.users.length
  const orgCount = scope.orgs.length
  const parts: string[] = []
  if (orgCount) parts.push(`组织 ${orgCount}`)
  if(scope.positions.length) parts.push(`岗位 ${scope.positions.length}`)
  if (scope.roles.length) parts.push(`角色 ${scope.roles.length}`)
  if (direct) parts.push(`单独添加 ${direct}`)
  return `人员 ${scope.grantTotal}${parts.length ? `（${parts.join(' · ')}）` : ''}`
}

function scopeChips(scope: Scope | null): Array<{ key: string; label: string }> {
  if (!scope) return []
  if (scope.scopeMode === 'PUBLIC') return [{ key: 'public', label: '公开 · 全公司可用' }]
  const chips: Array<{ key: string; label: string }> = []
  scope.orgs.forEach((o) => chips.push({ key: `o-${o.id}`, label: `组织 · ${o.name}` }))
  scope.positions.forEach((p) => chips.push({ key: `p-${p.id}`, label: `岗位 · ${p.name}` }))
  scope.roles.forEach((r) => chips.push({ key: `r-${r.id}`, label: `角色 · ${r.name}` }))
  scope.users.forEach((u) =>
    chips.push({ key: `u-${u.id}`, label: u.deptName ? `${u.name}（${u.deptName}）` : u.name })
  )
  return chips
}
</script>

<template>
  <div class="page-card">
    <div class="page-head">
      <div>
        <div class="page-title">审批中心</div>
        <div class="page-subtitle">集中处理共享申请、下架申请与范围变更，支持按列表或卡片查看。</div>
      </div>
      <div class="page-head-actions">
        <el-button @click="router.push('/assistants')">
          <span class="back-icon">←</span>返回列表
        </el-button>
        <div class="seg-group">
          <div class="seg" :class="{ active: view === 'list' }" @click="view = 'list'">列表</div>
          <div class="seg" :class="{ active: view === 'card' }" @click="view = 'card'">卡片</div>
        </div>
      </div>
    </div>

    <div v-if="!userStore.isAdmin" class="state-block">
      <span>暂无操作权限，审批中心仅公司管理员可访问</span>
    </div>

    <template v-else>
      <div class="list-meta">
        <span>共 {{ total }} 条待审批 · 按提交时间正序排列</span>
      </div>

      <div v-loading="loading" class="approval-wrap">
        <div v-if="loadError" class="state-block">
          <span>加载失败，点击重试</span>
          <el-button size="small" @click="loadList">重试</el-button>
        </div>

        <template v-else-if="list.length">
          <!-- 列表视图：行式，对齐原型 .appr-item -->
          <div v-if="view === 'list'" class="appr-list">
            <div v-for="row in list" :key="row.approvalId" class="appr-item" @click="openDetail(row.approvalId)">
              <AssistantAvatar
                :type="row.AssistantAvatar.type"
                :char="row.AssistantAvatar.char"
                :url="row.AssistantAvatar.url"
                :color="row.AssistantAvatar.color"
                :name="row.assistantName"
                :size="40"
              />
              <div class="appr-main">
                <div class="appr-name">
                  {{ row.assistantName }}
                  <el-tag size="small" :type="tagType(row.approvalType)" effect="light">
                    {{ typeLabel(row.approvalType) }}
                  </el-tag>
                  <span class="ver-tag">{{ row.assistantVersion }}</span>
                </div>
                <div class="appr-meta">提交人：{{ row.submitterName }} · {{ row.submitTime }}</div>
                <div class="appr-scope">{{ rowSubtitle(row) }}</div>
              </div>
              <span class="appr-arrow">›</span>
            </div>
          </div>

          <!-- 卡片视图：对齐原型 .appr-card -->
          <div v-else class="appr-grid">
            <div v-for="row in list" :key="row.approvalId" class="appr-card" @click="openDetail(row.approvalId)">
              <div class="appr-card-head">
                <AssistantAvatar
                  :type="row.AssistantAvatar.type"
                  :char="row.AssistantAvatar.char"
                  :url="row.AssistantAvatar.url"
                  :color="row.AssistantAvatar.color"
                  :name="row.assistantName"
                  :size="40"
                />
                <div class="appr-main">
                  <div class="appr-name">
                    {{ row.assistantName }}
                    <el-tag size="small" :type="tagType(row.approvalType)" effect="light">
                      {{ typeLabel(row.approvalType) }}
                    </el-tag>
                  </div>
                  <div class="appr-meta">{{ row.assistantVersion }} · 提交人：{{ row.submitterName }}</div>
                </div>
              </div>
              <div class="appr-scope">{{ rowSubtitle(row) }}</div>
              <div class="appr-card-foot">
                <span>{{ row.submitTime }}</span>
                <span class="appr-card-go">去处理 ›</span>
              </div>
            </div>
          </div>
        </template>

        <div v-else-if="!loading" class="appr-empty">
          <div class="empty-icon">✓</div>
          <div class="empty-text">暂无待审批的申请</div>
        </div>
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
    </template>

    <!-- ============ 审批详情抽屉 ============ -->
    <el-drawer v-model="detailOpen" :title="detail ? `审批详情 · ${detail.assistant.name}` : '审批详情'" size="760px" :close-on-click-modal="false">
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <div class="meta-line">{{ submitterLine }}</div>

          <div class="section-title">助理信息</div>
          <div class="expert-top">
            <AssistantAvatar
              :type="detail.assistant.avatar.type"
              :char="detail.assistant.avatar.char"
              :url="detail.assistant.avatar.url"
              :color="detail.assistant.avatar.color"
              :name="detail.assistant.name"
              :size="48"
            />
            <div class="expert-info">
              <div class="expert-name">
                {{ detail.assistant.name }}
                <span class="cat-tag">{{ detail.assistant.categoryName }}</span>
                <span class="ver-tag">{{ detail.assistant.version }}</span>
              </div>
              <div class="expert-tags">
                <span v-for="t in detail.assistant.tags" :key="t" class="mini-tag">{{ t }}</span>
              </div>
            </div>
          </div>

          <div class="cap-item">
            <div class="cap-title">描述</div>
            <div class="cap-body">{{ detail.assistant.description }}</div>
          </div>

          <el-alert
            v-if="detail.assistantConfigChanged"
            type="warning"
            :closable="false"
            show-icon
            title="助理配置在提交后已变更，请以最新配置为准"
            class="config-tip"
          />

          <!-- 下架申请：下架原因 + 当前授权范围 -->
          <template v-if="isOfflineType">
            <div class="section-title">下架原因</div>
            <div class="notice-bar">{{ detail.changeNote || '未填写' }}</div>
            <div class="section-title">当前授权范围</div>
            <div class="chip-list">
              <span v-for="c in scopeChips(detail.previousScope ?? detail.scope ?? null)" :key="c.key" class="chip">{{ c.label }}</span>
              <span v-if="!scopeChips(detail.previousScope ?? detail.scope ?? null).length" class="scope-empty">未设置</span>
            </div>
          </template>

          <!-- 范围变更：变更前 / 变更后 -->
          <template v-else-if="isScopeChangeType">
            <div class="section-title">授权范围变更</div>
            <div class="scope-block">
              <div class="scope-block-title">变更前</div>
              <div class="chip-list">
                <span v-for="c in scopeChips(detail.previousScope ?? null)" :key="c.key" class="chip">{{ c.label }}</span>
                <span v-if="!scopeChips(detail.previousScope ?? null).length" class="scope-empty">无</span>
              </div>
            </div>
            <div class="scope-block">
              <div class="scope-block-title">变更后</div>
              <div class="chip-list">
                <span v-for="c in scopeChips(detail.scope)" :key="c.key" class="chip">{{ c.label }}</span>
                <span v-if="!scopeChips(detail.scope).length" class="scope-empty">无</span>
              </div>
            </div>
            <div v-if="detail.changeNote" class="cap-item">
              <div class="cap-title">变更说明</div>
              <div class="cap-body">{{ detail.changeNote }}</div>
            </div>
          </template>

          <!-- 共享申请：能力组成（只读）+ 授权范围 -->
          <template v-else>
            <div class="section-title">能力组成（只读）</div>
            <div class="cap-item">
              <div class="cap-title">提示词</div>
              <div class="cap-body">{{ detail.assistant.prompt || '未配置' }}</div>
            </div>
            <div class="cap-item">
              <div class="cap-title">技能</div>
              <div class="cap-body">{{ detail.assistant.skills.map((s) => s.name).join('、') || '未配置' }}</div>
            </div>
            <div class="cap-item">
              <div class="cap-title">连接器</div>
              <div class="cap-body">{{ detail.assistant.mcps.map((m) => m.name).join('、') || '未配置' }}</div>
            </div>
            <div class="cap-item">
              <div class="cap-title">知识库</div>
              <div class="cap-body">{{ detail.assistant.knowledgeBases.map((k) => k.name).join('、') || '未配置' }}</div>
            </div>
            <div v-if="detail.changeNote" class="cap-item">
              <div class="cap-title">变更说明</div>
              <div class="cap-body">{{ detail.changeNote }}</div>
            </div>

            <div class="section-head">
              <span class="section-title">授权范围</span>
              <span v-if="detail.scopeAdjusted" class="adjusted-tag">已调整</span>
              <span v-if="detail.scope && !adjusting" class="scope-count">{{ scopePeopleLine(detail.scope) }}</span>
            </div>

            <template v-if="!adjusting">
              <div class="chip-list">
                <span v-for="c in scopeChips(detail.scope)" :key="c.key" class="chip">{{ c.label }}</span>
                <span v-if="!scopeChips(detail.scope).length" class="scope-empty">未设置</span>
              </div>
              <div v-if="detail.scopeDiff" class="diff-bar">
                较申请范围：新增 {{ detail.scopeDiff.addedCount }} 人，移除 {{ detail.scopeDiff.removedCount }} 人
              </div>
              <div v-if="currentActionable" class="adjust-line">
                <el-button size="small" @click="adjusting = true">调整授权范围</el-button>
              </div>
            </template>

            <template v-else>
              <ScopePicker v-model="scopePayload" />
              <div class="adjust-actions">
                <el-button size="small" type="primary" @click="saveAdjust">确认调整</el-button>
                <el-button size="small" @click="adjusting = false">取消</el-button>
              </div>
            </template>
          </template>
        </template>
      </div>

      <template #footer>
        <div v-if="currentActionable && detail" class="drawer-footer">
          <el-button @click="detailOpen = false">稍后处理</el-button>
          <el-button type="danger" :loading="deciding" @click="askReject">审批拒绝</el-button>
          <el-button type="primary" :loading="deciding" @click="askApprove">审批通过</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- ============ 通过确认弹窗 ============ -->
    <el-dialog v-model="confirmOpen" :title="confirmTitle" width="480px">
      <div class="confirm-text">{{ confirmText }}</div>
      <div class="confirm-impact">{{ confirmImpact }}</div>
      <template #footer>
        <el-button @click="confirmOpen = false">取消</el-button>
        <el-button type="primary" :loading="deciding" @click="confirmApprove">确认通过</el-button>
      </template>
    </el-dialog>

    <!-- ============ 拒绝弹窗 ============ -->
    <el-dialog v-model="rejectOpen" title="审批拒绝" width="520px">
      <div class="confirm-text">拒绝原因将展示在提交人的助理列表中，请说明具体问题。</div>
      <el-input
        v-model="rejectReason"
        type="textarea"
        :rows="4"
        maxlength="200"
        show-word-limit
        placeholder="请输入拒绝原因（1-200 字）"
      />
      <template #footer>
        <el-button @click="rejectOpen = false">取消</el-button>
        <el-button type="danger" :disabled="!rejectReason.trim()" :loading="deciding" @click="confirmReject">
          确认拒绝
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-head-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-icon {
  margin-right: 4px;
}

/* 胶囊分段：对齐原型 .seg-group */
.seg-group {
  display: flex;
  gap: 2px;
  padding: 3px;
  background: #edf2fa;
  border-radius: 999px;
}

.seg {
  padding: 4px 18px;
  border-radius: 999px;
  font-size: 13px;
  color: var(--at-text-sub);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.seg.active {
  background: #fff;
  color: var(--at-brand);
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(20, 27, 36, 0.14);
}

.list-meta {
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--at-text-weak);
}

.approval-wrap {
  min-height: 240px;
}

/* ---------- 列表视图 ---------- */
.appr-list {
  display: flex;
  flex-direction: column;
}

.appr-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 8px;
  border-bottom: 1px solid #eef0f3;
  cursor: pointer;
  transition: background 0.15s;
}

.appr-item:hover {
  background: #f7f9fc;
}

.appr-main {
  flex: 1;
  min-width: 0;
}

.appr-name {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--at-text);
}

.ver-tag {
  padding: 0 6px;
  border-radius: 3px;
  background: #f2f3f5;
  color: var(--at-text-sub);
  font-size: 11px;
  font-weight: 400;
  line-height: 18px;
}

.appr-meta {
  margin-top: 2px;
  font-size: 12px;
  color: var(--at-text-sub);
}

.appr-scope {
  margin-top: 4px;
  font-size: 12px;
  color: var(--at-text-weak);
}

.appr-arrow {
  color: #c9cdd4;
  font-size: 20px;
}

/* ---------- 卡片视图 ---------- */
.appr-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(272px, 1fr));
  gap: 12px;
  padding-top: 8px;
}

.appr-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  background: var(--at-bg-card);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(31, 35, 41, 0.08);
  cursor: pointer;
  transition: box-shadow 0.15s;
}

.appr-card:hover {
  box-shadow: 0 4px 14px rgba(31, 35, 41, 0.12);
}

.appr-card-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.appr-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--at-text-weak);
}

.appr-card-go {
  color: var(--at-brand);
  font-weight: 600;
}

/* ---------- 空态 ---------- */
.appr-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 80px 0;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #f0f9f4;
  color: #04b26a;
  font-size: 22px;
}

.empty-text {
  font-size: 13px;
  color: var(--at-text-weak);
}

/* ---------- 详情抽屉 ---------- */
.detail-body {
  min-height: 300px;
}

.meta-line {
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--at-text-sub);
}

.section-title {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--at-text);
}

.detail-body > .section-title:first-of-type {
  margin-top: 0;
}

.section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 16px 0 8px;
}

.section-head .section-title {
  margin: 0;
}

.expert-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.expert-info {
  flex: 1;
  min-width: 0;
}

.expert-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.cat-tag {
  padding: 0 6px;
  border: 1px solid #c8d6f0;
  border-radius: 3px;
  color: var(--at-brand);
  font-size: 11px;
  font-weight: 400;
  line-height: 18px;
}

.expert-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.mini-tag {
  padding: 0 6px;
  background: #f2f3f5;
  border-radius: 3px;
  color: var(--at-text-sub);
  font-size: 11px;
  line-height: 18px;
}

.cap-item {
  padding: 8px 12px;
  margin-bottom: 8px;
  background: #f7f8fa;
  border-radius: 6px;
}

.cap-title {
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--at-text-sub);
}

.cap-body {
  font-size: 13px;
  line-height: 1.7;
  color: var(--at-text);
  white-space: pre-wrap;
  word-break: break-word;
}

.config-tip {
  margin-bottom: 8px;
}

.notice-bar {
  padding: 8px 12px;
  background: #fff8e6;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: #8a5a00;
  white-space: pre-wrap;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  padding: 2px 8px;
  background: #f2f3f5;
  border-radius: 4px;
  font-size: 12px;
  line-height: 20px;
  color: var(--at-text-sub);
}

.scope-empty {
  font-size: 12px;
  color: var(--at-text-weak);
}

.scope-block {
  margin-bottom: 12px;
}

.scope-block-title {
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--at-text-weak);
}

.adjusted-tag {
  padding: 0 6px;
  background: #e8f8f0;
  border-radius: 3px;
  color: #04b26a;
  font-size: 11px;
  line-height: 18px;
}

.scope-count {
  margin-left: auto;
  font-size: 12px;
  color: var(--at-text-weak);
}

.diff-bar {
  margin-top: 8px;
  padding: 6px 10px;
  background: #f0f9f4;
  border-radius: 4px;
  font-size: 12px;
  color: #00875a;
}

.adjust-line {
  margin-top: 10px;
}

.adjust-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.confirm-text {
  font-size: 13px;
  line-height: 1.7;
  color: var(--at-text);
}

.confirm-impact {
  margin-top: 10px;
  padding: 8px 12px;
  background: #f7f8fa;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--at-text-sub);
}

.pager {
  display: flex;
  justify-content: center;
  padding-top: 20px;
}
</style>
