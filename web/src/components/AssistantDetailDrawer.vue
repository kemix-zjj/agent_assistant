<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AssistantAvatar from './AssistantAvatar.vue'
import StatusTag from './StatusTag.vue'
import { getAssistantDetail } from '@/api'
import { displayVersion } from '@/api/mock'
import { useUserStore } from '@/stores/user'
import type { AssistantAction, AssistantDetail } from '@/types/assistant'
import { ApiError } from '@/types/api'

/** 助理详情：对齐 prototype openDetail —— 760px 抽屉 + 分区纵向布局（无页签）
 *  区域顺序：头部 / 基础信息 / 能力组成（只读）/ 授权范围 / 版本记录
 */
const props = defineProps<{ modelValue: boolean; assistantId: number | null }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  action: [action: AssistantAction, card: AssistantDetail]
}>()

const userStore = useUserStore()

const detail = ref<AssistantDetail | null>(null)
const loading = ref(false)
/** 「无法删除该助理」提示弹窗 */
const cannotDeleteVisible = ref(false)

const ACTION_NAME: Record<string, string> = {
  create: '创建',
  update: '编辑更新',
  share_submit: '提交共享',
  share_approve: '共享审批通过',
  share_reject: '共享审批被拒绝',
  change_submit: '提交变更审批',
  change_approve: '变更审批通过（内容变更）',
  change_reject: '变更审批被拒绝',
  scope_change: '授权范围变更',
  scope_reject: '授权范围变更被拒绝',
  offline_submit: '提交下架申请',
  offline_approve: '下架生效',
  offline_reject: '下架申请被拒绝',
  delete: '删除'
}

const ACTION_LABEL: Record<string, string> = {
  summon: '召唤',
  edit: '编辑',
  delete: '删除',
  share: '共享',
  resubmit: '重新提交',
  shareScope: '修改授权范围',
  offline: '下架',
  remove: '移除',
  resubscribe: '重新订阅'
}

/** 已下架助理的 resubmit 语义为「重新共享」 */
function actionLabel(action: AssistantAction): string {
  if (action === 'resubmit' && detail.value?.shareStatus === 'offline') return '重新共享'
  return ACTION_LABEL[action]
}

/** 来源描述：平台内置 / 共享自 xx / 第三方接入 · 平台 / 创建人 xx */
const sourceLine = computed(() => {
  const d = detail.value
  if (!d) return ''
  if (d.source === 'platform') return '平台内置'
  if (d.source === 'shared') return `共享自 ${d.ownerName ?? ''}`
  if (d.source === 'thirdparty') return `第三方接入 · ${d.ownerName ?? ''}`
  return `创建人 ${d.ownerName ?? ''}`
})

/** 版本号：空串展示「未发布」 */
const versionText = computed(() => (detail.value ? displayVersion(detail.value.version) : ''))

/** 拒绝类型描述（与角标文案保持一致） */
const rejectTypeText = computed(() => {
  const map: Record<string, string> = {
    share: '共享审批',
    change: '调整审批',
    scope: '授权审批',
    offline: '下架审批'
  }
  return map[detail.value?.rejectType ?? 'share'] ?? '共享审批'
})

/** 技能 / 连接器 / 知识库的名称串（对齐原型 nameOf 的「、」连接） */
const skillsText = computed(() => (detail.value?.skills ?? []).map((s) => s.name).join('、') || '未配置')
const mcpsText = computed(() => (detail.value?.mcps ?? []).map((m) => m.name).join('、') || '未配置')
const kbsText = computed(() => (detail.value?.knowledgeBases ?? []).map((k) => k.name).join('、') || '未配置')

/** 授权范围 chips：来源（组织 / 角色 / 岗位）+ 生效人员 */
const scopeChips = computed(() => {
  const scope = detail.value?.shareScope
  if (!scope) return []
  if (scope.scopeMode === 'PUBLIC') return [{ key: 'public', label: '公开 · 全公司可用' }]
  return [
    ...scope.orgs.map((o) => ({ key: `org-${o.id}`, label: `组织 · ${o.name}` })),
    ...scope.roles.map((r) => ({ key: `role-${r.id}`, label: `角色 · ${r.name}` })),
    ...scope.positions.map((p) => ({ key: `pos-${p.id}`, label: `岗位 · ${p.name}` })),
    ...scope.users.map((u) => ({ key: `user-${u.id}`, label: u.name }))
  ]
})

/** 是否可调整授权范围：已共享，或已拒绝 · 授权审批；审批中（含下架审批中）不可改 */
const canEditScope = computed(() => {
  const d = detail.value
  if (!d) return false
  const isOwner = d.ownerName === userStore.currentUser.name || !d.ownerName
  const editable =
    d.shareStatus === 'approved' ||
    (d.rejectType === 'scope' && d.shareStatus === 'rejected')
  return editable && (isOwner || userStore.isAdmin)
})

/** 底部操作按钮：直接消费后端下发的 actions（与列表卡片同源，避免两套规则漂移） */
const footerActions = computed<AssistantAction[]>(() => detail.value?.actions ?? [])

/** 底部操作顺序与原型对齐：编辑 → 重新共享 → 下架 / 重新提交 → 删除 → 关闭 → 召唤
 *  授权范围调整入口统一放在「授权范围」分区标题右侧，底部不再重复出按钮。
 */
const FOOTER_ORDER: AssistantAction[] = [
  'edit',
  'resubmit',
  'offline',
  'share',
  'remove',
  'resubscribe',
  'delete'
]

const normalActions = computed(() =>
  FOOTER_ORDER.filter((a) => a !== 'delete' && footerActions.value.includes(a))
)
/** 危险操作：删除统一用红色文字按钮 */
const canDelete = computed(() => footerActions.value.includes('delete'))
const canSummon = computed(() => footerActions.value.includes('summon'))

watch(
  () => props.modelValue,
  async (open) => {
    if (!open || !props.assistantId) return
    loading.value = true
    try {
      detail.value = await getAssistantDetail(props.assistantId)
    } catch (e) {
      ElMessage.error(e instanceof ApiError ? e.message : '详情加载失败')
      emit('update:modelValue', false)
    } finally {
      loading.value = false
    }
  }
)

function onAction(action: AssistantAction): void {
  if (!detail.value) return
  // 已拒绝 · 调整/授权/下架审批曾共享成功，点击删除仅提示不可删除
  if (
    action === 'delete' &&
    detail.value.shareStatus === 'rejected' &&
    detail.value.rejectType !== 'share'
  ) {
    // 与原型一致：关闭详情抽屉后弹出提示
    emit('update:modelValue', false)
    cannotDeleteVisible.value = true
    return
  }
  emit('action', action, detail.value)
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    size="760px"
    :close-on-click-modal="false"
    :title="detail ? `助理详情 · ${detail.name}` : '助理详情'"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <div v-loading="loading" class="detail-body">
      <template v-if="detail">
        <!-- 头部：头像 52 + 名称 / 状态 / 版本 + 来源信息 + 标签 -->
        <div class="detail-head">
          <AssistantAvatar
            :type="detail.avatarType"
            :char="detail.avatarChar"
            :url="detail.avatarUrl"
            :color="detail.avatarColor"
            :name="detail.name"
            :seed="detail.assistantId"
            :size="52"
          />
          <div class="head-main">
            <div class="detail-name">
              <span>{{ detail.name }}</span>
              <StatusTag
                v-if="detail.shareStatus"
                :status="detail.shareStatus"
                :pending-type="detail.pendingType"
                :reject-type="detail.rejectType"
              />
              <span class="ver-tag">{{ versionText }}</span>
            </div>
            <div class="detail-meta">
              {{ detail.categoryName }} · {{ sourceLine }} · 更新于 {{ detail.updatedAt }}
            </div>
            <div class="head-tags">
              <span v-for="t in detail.tags" :key="t" class="mini-tag">{{ t }}</span>
            </div>
          </div>
        </div>

        <!-- 基础信息 -->
        <div class="detail-section">
          <div class="detail-section-title">基础信息</div>
          <div class="cap-item">
            <div class="cap-title">描述</div>
            <div class="cap-body">{{ detail.description || '未填写' }}</div>
          </div>
          <!-- 已拒绝：展示拒绝类型与原因（卡片上不展示原因，仅详情可见） -->
          <div v-if="detail.shareStatus === 'rejected'" class="notice-bar is-error">
            <span>
              拒绝类型：{{ rejectTypeText }} · 拒绝原因：{{ detail.rejectReason || '管理员未填写拒绝原因' }}
            </span>
          </div>
          <div
            v-if="detail.shareStatus === 'pending' && detail.pendingType === 'offline' && detail.offlineReason"
            class="notice-bar is-warning"
          >
            <span>下架原因：{{ detail.offlineReason }}（等待管理员审批）</span>
          </div>
          <div
            v-if="detail.shareStatus === 'pending' && detail.pendingType === 'scope'"
            class="notice-bar is-info"
          >
            <span>授权范围变更审批中：审批期间原授权范围继续生效，审批通过后切换为新范围。</span>
          </div>
          <!-- 授权范围变更被拒提示：仅创建人 / 管理员可见（被授权方接口已折叠审批信息） -->
          <div v-if="detail.rejectType === 'scope'" class="notice-bar is-info">
            <span>授权范围变更未通过：本次变更不生效，原共享范围与已订阅用户不受影响，可重新提交授权范围变更。</span>
          </div>
        </div>

        <!-- 能力组成（只读） -->
        <div class="detail-section">
          <div class="detail-section-title">能力组成（只读）</div>
          <div class="cap-item">
            <div class="cap-title">提示词</div>
            <div class="cap-body">{{ detail.prompt || '未配置' }}</div>
          </div>
          <div class="cap-item">
            <div class="cap-title">技能</div>
            <div class="cap-body">{{ skillsText }}</div>
          </div>
          <div class="cap-item">
            <div class="cap-title">连接器</div>
            <div class="cap-body">{{ mcpsText }}</div>
          </div>
          <div class="cap-item">
            <div class="cap-title">知识库</div>
            <div class="cap-body">{{ kbsText }}</div>
          </div>
          <div class="cap-item">
            <div class="cap-title">召唤快速问题</div>
            <div class="cap-body">
              <template v-if="detail.quickQuestions.length">
                · {{ detail.quickQuestions.join('\n· ') }}
              </template>
              <span v-else class="scope-empty">未配置</span>
            </div>
          </div>
        </div>

        <!-- 授权范围：仅已共享助理展示；调整入口只在此分区，底部不重复 -->
        <div v-if="detail.shareScope" class="detail-section">
          <div class="detail-section-title">
            <span>授权范围</span>
            <button v-if="canEditScope" class="section-link" @click="onAction('shareScope')">
              修改授权范围
            </button>
          </div>
          <div class="scope-chips">
            <span v-for="c in scopeChips" :key="c.key" class="scope-chip">{{ c.label }}</span>
          </div>
          <div class="form-hint">
            已授权 {{ detail.shareScope.grantTotal }} 个对象（{{ detail.shareScope.summary || '未设置' }}）
          </div>
        </div>

        <!-- 版本记录 -->
        <div class="detail-section">
          <div class="detail-section-title">
            <span>版本记录</span>
            <span class="section-hint">编辑保存会生成新版本，已共享的助理需重新审批</span>
          </div>
          <div v-if="detail.versionHistory.length" class="ver-list">
            <div v-for="h in detail.versionHistory" :key="`${h.version}-${h.createdAt}`" class="ver-item">
              <span class="ver-no">{{ h.version }}</span>
              <div class="ver-main">
                <div class="ver-action">{{ ACTION_NAME[h.action] ?? h.actionName }}</div>
                <div class="ver-meta">
                  {{ h.operatorName }} · {{ h.createdAt }}<template v-if="h.remark"> · {{ h.remark }}</template>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="scope-empty">暂无版本记录</div>
        </div>
      </template>
    </div>

    <template v-if="detail" #footer>
      <div class="drawer-footer-inner">
        <button
          v-for="a in normalActions"
          :key="a"
          :class="['btn', a === 'offline' ? 'btn-danger-text' : 'btn-default']"
          @click="onAction(a)"
        >
          {{ actionLabel(a) }}
        </button>
        <button v-if="canDelete" class="btn btn-danger-text" @click="onAction('delete')">
          {{ ACTION_LABEL.delete }}
        </button>
        <button class="btn btn-default" @click="emit('update:modelValue', false)">关闭</button>
        <button v-if="canSummon" class="btn btn-primary" @click="onAction('summon')">召唤</button>
      </div>
    </template>
  </el-drawer>

  <el-dialog
    v-model="cannotDeleteVisible"
    width="480px"
    class="cannot-delete-dialog"
    modal-class="cannot-delete-overlay"
    :show-close="false"
    append-to-body
  >
    <template #header>
      <div class="nd-head">
        <span class="nd-title">无法删除该助理</span>
        <!-- <button class="nd-close" aria-label="关闭" @click="cannotDeleteVisible = false">×</button> -->
      </div>
    </template>
    <div class="nd-notice">
      <svg class="nd-icon" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
        <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" stroke-width="1.4" />
        <path d="M8 4.4v4.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
        <circle cx="8" cy="11.4" r="0.9" fill="currentColor" />
      </svg>
      <span>该助理已共享过，无法删除，请进行下架处理。</span>
    </div>
    <template #footer>
      <el-button type="primary" class="nd-btn" @click="cannotDeleteVisible = false">我知道了</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.detail-body {
  min-height: 300px;
}

/* ---------- 头部：对齐 prototype .detail-head ---------- */
.detail-head {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}

.head-main {
  flex: 1;
  min-width: 0;
}

.detail-name {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--at-text);
}

.ver-tag {
  font-size: 11px;
  font-weight: 400;
  color: var(--at-text-weak);
  font-family: var(--font-mono, monospace);
}

.detail-meta {
  margin: 4px 0 6px;
  font-size: 12px;
  color: var(--at-text-sub);
}

.head-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.mini-tag {
  padding: 2px 10px;
  background: #fff;
  border: 1px solid var(--at-border);
  border-radius: 999px;
  color: var(--at-text-sub);
  font-size: 11px;
  line-height: 16px;
}

/* ---------- 分区 ---------- */
.detail-section {
  margin-bottom: 24px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--at-brand);
}

.section-link {
  padding: 0;
  border: none;
  background: none;
  color: var(--at-brand);
  font-size: 12px;
  cursor: pointer;
}

.section-link:hover {
  text-decoration: underline;
}

.section-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--at-text-weak);
}

/* ---------- 只读配置块：对齐 prototype .cap-item ---------- */
.cap-item {
  padding: 8px 12px;
  background: #f4f7f9;
  border-radius: 4px;
  margin-bottom: 8px;
}

.cap-item:last-child {
  margin-bottom: 0;
}

.cap-title {
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--at-text-sub);
}

.cap-body {
  font-size: 12px;
  line-height: 1.7;
  color: var(--at-text);
  white-space: pre-wrap;
  max-height: 132px;
  overflow: auto;
  word-break: break-word;
}

.no-permission {
  padding: 24px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--at-text-weak);
  background: #f4f7f9;
  border-radius: 4px;
}

/* ---------- 授权范围 ---------- */
.scope-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.scope-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  font-size: 12px;
  color: #2563c9;
  background: #eef4ff;
  border: 1px solid #d6e4ff;
  border-radius: 2px;
}

.form-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--at-text-weak);
}

.scope-empty {
  font-size: 12px;
  color: var(--at-text-weak);
}

/* ---------- 提示条：拒绝 / 下架 / 审批说明 ---------- */
.notice-bar {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 8px;
  padding: 8px 12px;
  font-size: 12px;
  line-height: 1.7;
  border-radius: 4px;
}

.notice-bar.is-error {
  color: #d92d20;
  background: #fff6f5;
}

.notice-bar.is-warning {
  color: #d25f00;
  background: #fff7e8;
}

.notice-bar.is-info {
  color: #2563c9;
  background: #eef4ff;
}

/* ---------- 版本记录：对齐 prototype .ver-item ---------- */
.ver-list {
  display: flex;
  flex-direction: column;
}

.ver-item {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px dashed var(--at-border);
}

.ver-item:last-child {
  border-bottom: 0;
}

.ver-no {
  flex: 0 0 48px;
  font-size: 12px;
  font-weight: 600;
  color: var(--at-brand);
}

.ver-main {
  flex: 1;
  min-width: 0;
}

.ver-action {
  font-size: 12px;
  color: var(--at-text);
}

.ver-meta {
  margin-top: 2px;
  font-size: 11px;
  color: var(--at-text-weak);
}

/* ---------- 底部按钮：右对齐，对齐 prototype .drawer-footer ---------- */
.drawer-footer-inner {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}

.btn {
  height: 32px;
  padding: 6px 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid transparent;
  border-radius: 4px;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-default {
  background: #fff;
  color: var(--at-text-sub);
  border-color: var(--at-border);
}

.btn-default:hover {
  color: var(--at-brand);
  border-color: var(--at-brand);
}

.btn-danger-text {
  background: none;
  border: none;
  color: var(--at-danger);
  font-weight: 400;
  padding: 4px 8px;
}

.btn-danger-text:hover {
  background: #ffefee;
}

.btn-primary {
  background: var(--at-brand);
  border-color: var(--at-brand);
  color: #fff;
}

.btn-primary:hover {
  background: #2468f2;
  border-color: #2468f2;
}
</style>

<style>
/* 「无法删除该助理」弹窗：完全对齐 prototype 的 .modal + .notice-bar */
.cannot-delete-overlay .el-overlay-dialog {
  display: flex;
  align-items: center;
  justify-content: center;
}

.cannot-delete-dialog.el-dialog {
  display: flex;
  flex-direction: column;
  min-height: 36vh;
  margin: 0;
  padding: 0;
  overflow: hidden;
  border-radius: 4px;
  box-shadow: 0 12px 30px rgba(20, 27, 36, 0.18);
}

.cannot-delete-dialog .el-dialog__header {
  margin: 0;
  padding: 0;
}

.cannot-delete-dialog .el-dialog__body {
  flex: 1;
  padding: 16px;
}

.cannot-delete-dialog .el-dialog__footer {
  padding: 12px 16px;
  border-top: 1px solid #e4e7f0;
}

.cannot-delete-dialog .nd-head {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 16px;
  background: var(--at-header-bg);
}

.cannot-delete-dialog .nd-title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.cannot-delete-dialog .nd-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  font-size: 18px;
  line-height: 1;
  color: #fff;
  background: none;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.cannot-delete-dialog .nd-close:hover {
  background: rgba(255, 255, 255, 0.15);
}

.cannot-delete-dialog .nd-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 10px 16px;
  font-size: 12px;
  line-height: 1.6;
  color: #d46b08;
  background: #fff7e8;
  border-radius: 4px;
}

.cannot-delete-dialog .nd-icon {
  flex-shrink: 0;
  color: #ff813b;
}

.cannot-delete-dialog .nd-btn {
  height: 32px;
  margin-top: 8px;
  padding: 0 14px;
  font-weight: 600;
}
</style>
