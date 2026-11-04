<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
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
import type { ScopePayload, ScopeMode } from '@/types/scope'
import { ApiError } from '@/types/api'

/** 审批中心：待审批列表（列表 / 卡片双视图）+ 详情 + 范围调整 + 通过 / 拒绝（F-APR-001~003） */
const router = useRouter()
const userStore = useUserStore()
const approvalStore = useApprovalStore()

const view = ref<'list' | 'card'>('list')
const typeFilter = ref<string>('')
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
const comment = ref('')
const deciding = ref(false)

const TYPE_OPTIONS = [
  { value: '', label: '全部类型' },
  { value: 'share', label: '共享申请' },
  { value: 'scope_change', label: '范围变更' }
]

const currentActionable = computed(() => detail.value?.status === 'pending')

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
    const res = await getApprovals({
      status: 'pending',
      approvalType: typeFilter.value || undefined,
      page: page.value,
      pageSize
    })
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

async function openDetail(approvalId: number): Promise<void> {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = null
  adjusting.value = false
  comment.value = ''
  try {
    const d = await getApprovalDetail(approvalId)
    detail.value = d
    scopePayload.value = {
      scopeMode: d.scope.scopeMode as ScopeMode,
      orgs: d.scope.orgs.map((o) => o.id),
      roles: d.scope.roles.map((r) => r.id),
      positions: d.scope.positions.map((p) => p.id),
      users: d.scope.users.map((u) => u.id)
    }
  } catch (e) {
    if (e instanceof ApiError && e.code === 'APPROVAL_ALREADY_HANDLED') {
      ElMessage.warning('该申请已被处理，列表已刷新')
      detailOpen.value = false
      await loadList()
      await approvalStore.refreshPendingCount()
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
    ElMessage.warning('请至少选择一个组织或人员')
    return
  }
  try {
    const res = await adjustApprovalScope(detail.value.approvalId, p)
    detail.value.scope = res.scope
    detail.value.scopeDiff = res.scopeDiff
    detail.value.scopeAdjusted = true
    adjusting.value = false
    ElMessage.success('授权范围已暂存，审批通过后生效')
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '范围调整失败')
  }
}

async function handleApprove(): Promise<void> {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(
      '审批通过后，授权范围将立即生效并通知提交人，确认通过？',
      '审批通过',
      { type: 'info', confirmButtonText: '确认通过', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  deciding.value = true
  try {
    await approveApproval(detail.value.approvalId, comment.value.trim() || undefined)
    ElMessage.success('已通过')
    detailOpen.value = false
    await afterDecision()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '审批失败，请稍后重试')
  } finally {
    deciding.value = false
  }
}

async function handleReject(): Promise<void> {
  if (!detail.value) return
  let reason = ''
  try {
    const result = await ElMessageBox.prompt('拒绝原因将展示给提交人，请说明需要调整的内容。', '审批拒绝', {
      confirmButtonText: '确认拒绝',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputPlaceholder: '1-200 字',
      inputValidator: (v: string) => {
        if (!v || !v.trim()) return '请填写拒绝原因'
        if (v.length > 200) return '原因最多 200 字'
        return true
      }
    })
    reason = result.value.trim()
  } catch {
    return
  }
  deciding.value = true
  try {
    await rejectApproval(detail.value.approvalId, reason)
    ElMessage.success('已拒绝')
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

function scopeModeText(mode: string): string {
  return mode === 'PUBLIC' ? '公开' : '范围授权'
}
</script>

<template>
  <div class="page-card">
    <div class="page-head">
      <div>
        <div class="page-title">审批中心</div>
        <div class="page-subtitle">审批助理共享申请，可在通过前调整授权范围。</div>
      </div>
      <el-button @click="router.push('/assistants')">返回助理列表</el-button>
    </div>

    <div v-if="!userStore.isAdmin" class="state-block">
      <span>暂无操作权限，审批中心仅公司管理员可访问</span>
    </div>

    <template v-else>
      <div class="filter-bar">
        <el-select v-model="typeFilter" class="type-select" @change="page = 1; loadList()">
          <el-option v-for="o in TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <div class="view-switch">
          <span class="view-label">视图</span>
          <el-radio-group v-model="view" size="small">
            <el-radio-button value="list">列表</el-radio-button>
            <el-radio-button value="card">卡片</el-radio-button>
          </el-radio-group>
        </div>
        <span class="filter-meta">待审批 {{ total }} 条</span>
      </div>

      <div v-loading="loading" class="approval-wrap">
        <div v-if="loadError" class="state-block">
          <span>加载失败，点击重试</span>
          <el-button size="small" @click="loadList">重试</el-button>
        </div>

        <template v-else-if="list.length">
          <!-- 列表视图 -->
          <el-table v-if="view === 'list'" :data="list" class="approval-table" @row-click="(row: ApprovalCard) => openDetail(row.approvalId)">
            <el-table-column label="助理" min-width="200">
              <template #default="{ row }">
                <div class="cell-assistant">
                  <AssistantAvatar
                    :type="row.AssistantAvatar.type"
                    :char="row.AssistantAvatar.char"
                    :url="row.AssistantAvatar.url"
                    :color="row.AssistantAvatar.color"
                    :name="row.assistantName"
                    :size="32"
                  />
                  <div class="cell-info">
                    <div class="cell-name">{{ row.assistantName }}</div>
                    <div class="cell-sub">{{ row.categoryName }} · {{ row.assistantVersion }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="approvalTypeName" label="类型" width="100" />
            <el-table-column label="提交人" width="150">
              <template #default="{ row }">
                <div>{{ row.submitterName }}</div>
                <div class="cell-sub">{{ row.submitterDept }}</div>
              </template>
            </el-table-column>
            <el-table-column label="授权范围" min-width="200">
              <template #default="{ row }">
                <span class="scope-text">{{ row.scopeSummary }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="submitTime" label="提交时间" width="160" />
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click.stop="openDetail(row.approvalId)">审批</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 卡片视图 -->
          <div v-else class="approval-grid">
            <div v-for="row in list" :key="row.approvalId" class="approval-card" @click="openDetail(row.approvalId)">
              <div class="ac-head">
                <AssistantAvatar
                  :type="row.AssistantAvatar.type"
                  :char="row.AssistantAvatar.char"
                  :url="row.AssistantAvatar.url"
                  :color="row.AssistantAvatar.color"
                  :name="row.assistantName"
                  :size="40"
                />
                <div class="ac-info">
                  <div class="ac-name">{{ row.assistantName }}</div>
                  <div class="ac-meta">{{ row.categoryName }} · {{ row.assistantVersion }}</div>
                </div>
                <el-tag size="small" type="warning">{{ row.approvalTypeName }}</el-tag>
              </div>
              <div class="ac-tags">
                <span v-for="t in row.tags.slice(0, 3)" :key="t" class="mini-tag">{{ t }}</span>
              </div>
              <div class="ac-row">
                <span class="ac-label">提交人</span>
                <span>{{ row.submitterName }} · {{ row.submitterDept }}</span>
              </div>
              <div class="ac-row">
                <span class="ac-label">授权范围</span>
                <span class="scope-text">{{ row.scopeSummary }}</span>
              </div>
              <div class="ac-foot">
                <span class="ac-time">{{ row.submitTime }}</span>
                <el-button type="primary" size="small">去审批</el-button>
              </div>
            </div>
          </div>
        </template>

        <div v-else-if="!loading" class="state-block">暂无待审批申请</div>
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

    <el-drawer v-model="detailOpen" title="审批详情" size="680px" :close-on-click-modal="false">
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <div class="detail-head">
            <AssistantAvatar
              :type="detail.assistant.avatar.type"
              :char="detail.assistant.avatar.char"
              :url="detail.assistant.avatar.url"
              :color="detail.assistant.avatar.color"
              :name="detail.assistant.name"
              :size="48"
            />
            <div class="head-info">
              <div class="head-name">{{ detail.assistant.name }}</div>
              <div class="head-meta">{{ detail.assistant.categoryName }} · {{ detail.assistant.version }} · {{ detail.assistant.ownerName }}</div>
            </div>
            <el-tag size="small" type="warning">待审批</el-tag>
          </div>

          <el-alert
            v-if="detail.assistantConfigChanged"
            type="warning"
            :closable="false"
            show-icon
            title="助理配置在提交后已变更，请以最新配置为准"
            class="config-tip"
          />

          <div class="section">
            <div class="section-title">申请信息</div>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="审批单号">{{ detail.approvalNo }}</el-descriptions-item>
              <el-descriptions-item label="提交时间">{{ detail.submitTime }}</el-descriptions-item>
              <el-descriptions-item label="提交人">{{ detail.submitterName }}</el-descriptions-item>
              <el-descriptions-item label="所属部门">{{ detail.submitterDept }}</el-descriptions-item>
            </el-descriptions>
          </div>

          <div class="section">
            <div class="section-title">助理配置（只读）</div>
            <div class="config-desc">{{ detail.assistant.description }}</div>
            <pre class="prompt-view">{{ detail.assistant.prompt }}</pre>
          </div>

          <div class="section">
            <div class="section-head">
              <span class="section-title">授权范围</span>
              <el-tag v-if="detail.scopeAdjusted" size="small" type="success">已调整</el-tag>
              <span class="scope-mode">{{ scopeModeText(detail.scope.scopeMode) }} · {{ detail.scope.grantTotal }} 人</span>
              <el-button
                v-if="currentActionable && !adjusting"
                link
                type="primary"
                size="small"
                class="adjust-btn"
                @click="adjusting = true"
              >
                调整授权范围
              </el-button>
            </div>

            <template v-if="!adjusting">
              <div class="scope-summary">{{ detail.scope.summary }}</div>
              <div class="chip-list">
                <el-tag v-for="o in detail.scope.orgs" :key="`o-${o.id}`" size="small" type="info">组织 · {{ o.name }}</el-tag>
                <el-tag v-for="p in detail.scope.positions" :key="`p-${p.id}`" size="small" type="info">岗位 · {{ p.name }}</el-tag>
                <el-tag v-for="r in detail.scope.roles" :key="`r-${r.id}`" size="small" type="info">角色 · {{ r.name }}</el-tag>
                <el-tag v-for="u in detail.scope.users" :key="`u-${u.id}`" size="small" type="info">{{ u.name }}</el-tag>
              </div>
              <div v-if="detail.scopeDiff" class="diff-bar">
                较申请范围：新增 {{ detail.scopeDiff.addedCount }} 人，移除 {{ detail.scopeDiff.removedCount }} 人
              </div>
            </template>

            <template v-else>
              <ScopePicker v-model="scopePayload" />
              <div class="adjust-actions">
                <el-button size="small" @click="adjusting = false">取消</el-button>
                <el-button size="small" type="primary" @click="saveAdjust">暂存调整</el-button>
              </div>
            </template>
          </div>

          <div v-if="currentActionable" class="section">
            <div class="section-title">审批意见（选填）</div>
            <el-input v-model="comment" type="textarea" :rows="2" maxlength="200" placeholder="通过时可填写意见" />
          </div>
        </template>
      </div>

      <template #footer>
        <div v-if="currentActionable && detail" class="drawer-footer">
          <el-button :loading="deciding" @click="handleReject">拒绝</el-button>
          <el-button type="primary" :loading="deciding" @click="handleApprove">通过</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.type-select {
  width: 140px;
}

.view-switch {
  display: flex;
  align-items: center;
  gap: 8px;
}

.view-label {
  font-size: 12px;
  color: var(--at-text-weak);
}

.filter-meta {
  margin-left: auto;
  font-size: 12px;
  color: var(--at-text-weak);
}

.approval-wrap {
  min-height: 240px;
}

.approval-table {
  width: 100%;
}

.approval-table :deep(.el-table__row) {
  cursor: pointer;
}

.cell-assistant {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cell-name {
  font-size: 13px;
  font-weight: 500;
}

.cell-sub {
  font-size: 12px;
  color: var(--at-text-weak);
}

.scope-text {
  font-size: 12px;
  color: var(--at-text-sub);
}

.approval-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

.approval-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid var(--at-border);
  border-radius: 6px;
  cursor: pointer;
  transition: box-shadow 0.15s, border-color 0.15s;
}

.approval-card:hover {
  border-color: #c8d6f0;
  box-shadow: 0 2px 10px rgba(31, 35, 41, 0.06);
}

.ac-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ac-info {
  flex: 1;
  min-width: 0;
}

.ac-name {
  font-size: 14px;
  font-weight: 600;
}

.ac-meta {
  font-size: 12px;
  color: var(--at-text-weak);
}

.ac-tags {
  display: flex;
  gap: 4px;
}

.mini-tag {
  padding: 0 6px;
  background: #f2f3f5;
  border-radius: 3px;
  color: var(--at-text-sub);
  font-size: 11px;
  line-height: 18px;
}

.ac-row {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--at-text-sub);
}

.ac-label {
  flex: 0 0 56px;
  color: var(--at-text-weak);
}

.ac-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 8px;
  border-top: 1px solid #f2f3f5;
}

.ac-time {
  font-size: 12px;
  color: var(--at-text-weak);
}

.detail-body {
  min-height: 300px;
}

.detail-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--at-border);
}

.head-info {
  flex: 1;
}

.head-name {
  font-size: 16px;
  font-weight: 600;
}

.head-meta {
  margin-top: 2px;
  font-size: 12px;
  color: var(--at-text-sub);
}

.config-tip {
  margin-top: 12px;
}

.section {
  margin-top: 18px;
}

.section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.section-title {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 8px;
}

.section-head .section-title {
  margin-bottom: 0;
}

.scope-mode {
  font-size: 12px;
  color: var(--at-text-weak);
}

.adjust-btn {
  margin-left: auto;
}

.config-desc {
  font-size: 12px;
  line-height: 20px;
  color: var(--at-text-sub);
  margin-bottom: 8px;
}

.prompt-view {
  margin: 0;
  padding: 10px 12px;
  background: #f7f8fa;
  border-radius: 4px;
  font-family: inherit;
  font-size: 12px;
  line-height: 20px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--at-text-sub);
  max-height: 180px;
  overflow-y: auto;
}

.scope-summary {
  font-size: 13px;
  margin-bottom: 8px;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.diff-bar {
  margin-top: 8px;
  padding: 6px 10px;
  background: #f0f9f4;
  border-radius: 4px;
  font-size: 12px;
  color: #00875a;
}

.adjust-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.pager {
  display: flex;
  justify-content: center;
  padding-top: 20px;
}
</style>
