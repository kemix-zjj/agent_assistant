<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AssistantAvatar from './AssistantAvatar.vue'
import StatusTag from './StatusTag.vue'
import { getAssistantDetail } from '@/api'
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

const ACTION_NAME: Record<string, string> = {
  create: '创建',
  update: '编辑更新',
  share_submit: '提交共享',
  share_approve: '审批通过',
  share_reject: '审批拒绝',
  scope_change: '授权范围变更',
  offline_submit: '提交下架',
  offline_approve: '下架生效',
  offline_reject: '下架被拒',
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

/** 来源描述：平台预置 / 共享自 xx / 第三方接入 · 平台 / 创建人 xx */
const sourceLine = computed(() => {
  const d = detail.value
  if (!d) return ''
  if (d.source === 'platform') return '平台预置'
  if (d.source === 'shared') return `共享自 ${d.ownerName ?? ''}`
  if (d.source === 'thirdparty') return `第三方接入 · ${d.ownerName ?? ''}`
  return `创建人 ${d.ownerName ?? ''}`
})

/** 是否被授权方视角：提示词与能力组成不可见（需求 5.2） */
const readonlyView = computed(() => !!detail.value && detail.value.prompt === null)

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

/** 是否可调整授权范围：已共享 / 下架审批中的助理，创建人或公司管理员可改 */
const canEditScope = computed(() => {
  const d = detail.value
  if (!d) return false
  const isOwner = !d.ownerName || d.ownerName === userStore.currentUser.name
  return d.shareStatus === 'approved' && (isOwner || userStore.isAdmin)
})

/** 底部操作按钮：沿用列表卡片的 actions 语义（详情响应不带 actions，按状态推导）
 *  授权范围调整入口统一放在「授权范围」分区标题右侧，底部不再重复出按钮。
 */
const footerActions = computed<AssistantAction[]>(() => {
  const d = detail.value
  if (!d) return []
  const actions: AssistantAction[] = []
  const isOwner = !d.ownerName || d.ownerName === userStore.currentUser.name

  if (readonlyView.value) return ['remove']
  // 平台预置助理没有授权范围快照分区，管理员的范围授权入口保留在底部
  if (d.source === 'platform') {
    return userStore.isAdmin ? ['shareScope', 'summon'] : ['summon']
  }
  if (!isOwner) return ['summon']
  switch (d.shareStatus) {
    case 'unshared':
      actions.push('share', 'edit', 'delete', 'summon')
      break
    case 'pending':
      actions.push('edit', 'delete', 'summon')
      break
    case 'approved':
      // 已共享：编辑 / 下架 / 召唤（授权范围在分区标题内调整，底部不重复）
      actions.push('edit', 'offline', 'summon')
      break
    case 'rejected':
      // 被拒绝后仍可继续编辑，调整后重新提交审批
      actions.push('edit', 'resubmit', 'delete', 'summon')
      break
    case 'offline_pending':
      // 下架审批中：不可编辑与召唤
      actions.push('edit', 'summon')
      break
    default:
      actions.push('edit', 'summon')
  }
  return actions
})

const sideActions = computed(() =>
  footerActions.value.filter((a) => {
    if (a === 'summon' || a === 'delete' || a === 'remove' || a === 'offline') return false
    // 授权范围分区已提供「修改授权范围」入口时，底部不再重复
    if (a === 'shareScope' && canEditScope.value) return false
    return true
  })
)
/** 危险操作：删除 / 下架 / 移除，统一用红色文字按钮 */
const dangerActions = computed(() =>
  footerActions.value.filter((a) => a === 'delete' || a === 'offline' || a === 'remove')
)
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
              <StatusTag v-if="detail.shareStatus" :status="detail.shareStatus" />
              <span class="ver-tag">{{ detail.version }}</span>
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
        </div>

        <!-- 能力组成（只读） -->
        <div class="detail-section">
          <div class="detail-section-title">能力组成（只读）</div>
          <div v-if="readonlyView" class="no-permission">
            共享助理由创建人维护，被授权方仅可召唤使用，不可查看配置。
          </div>
          <template v-else>
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
          </template>
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
          v-for="a in sideActions"
          :key="a"
          class="btn"
          :class="a === 'edit' ? 'btn-default' : 'btn-default'"
          @click="onAction(a)"
        >
          {{ ACTION_LABEL[a] }}
        </button>
        <button
          v-for="a in dangerActions"
          :key="a"
          class="btn btn-danger-text"
          @click="onAction(a)"
        >
          {{ ACTION_LABEL[a] }}
        </button>
        <button class="btn btn-default" @click="emit('update:modelValue', false)">关闭</button>
        <button v-if="canSummon" class="btn btn-primary" @click="onAction('summon')">召唤</button>
      </div>
    </template>
  </el-drawer>
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
