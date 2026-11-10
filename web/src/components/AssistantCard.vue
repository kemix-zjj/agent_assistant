<script setup lang="ts">
import { computed } from 'vue'
import AssistantAvatar from './AssistantAvatar.vue'
import StatusTag from './StatusTag.vue'
import { useUserStore } from '@/stores/user'
import type { AssistantCard, AssistantAction } from '@/types/assistant'

/** 助理卡片：列表页四范围共用，按钮由后端 actions 驱动
 * 整卡点击进详情；召唤按钮默认常驻，悬停有渐变、描边与轻微上浮动效；标签最多 2 个其余 +N。
 */
const props = defineProps<{
  card: AssistantCard
  scope?: 'all' | 'mine' | 'shared' | 'auth'
  selectable?: boolean
  selected?: boolean
  expandedReject?: boolean
}>()

const emit = defineEmits<{
  action: [action: AssistantAction | 'detail' | 'toggleReject', card: AssistantCard]
  'update:selected': [value: boolean]
}>()

const ACTION_LABEL: Record<AssistantAction, string> = {
  summon: '召唤',
  edit: '编辑',
  delete: '删除',
  share: '共享',
  resubmit: '重新提交',
  shareScope: '共享范围',
  offline: '下架',
  remove: '移除',
  resubscribe: '重新订阅'
}

const userStore = useUserStore()
/** 授权管理页签：卡片常驻「详情 / 调整范围」，其余范围仅展示召唤（悬停） */
const isAuthView = computed(() => props.scope === 'auth')

/**
 * 卡片按钮：需求 F-EXP-002 平台预置授权范围仅管理员可见；
 * 编辑/删除/共享/重新提交只出现在「我的助理」，其余操作收进详情抽屉。
 */
const visibleActions = computed<AssistantAction[]>(() => {
  const actions = props.card.actions ?? []
  if (isAuthView.value) {
    return actions.includes('shareScope') && userStore.isAdmin ? ['shareScope'] : []
  }
  return actions.filter((a) => a === 'summon')
})

const canShare = computed(
  () =>
    props.scope === 'mine' &&
    props.card.source !== 'shared' &&
    (props.card.shareStatus === 'unshared' || props.card.shareStatus === 'rejected')
)

/** 标签：最多展示 2 个，其余以 +N 收拢（完整标签见详情） */
const visibleTags = computed(() => props.card.tags.slice(0, 2))
const moreTagCount = computed(() => Math.max(props.card.tags.length - 2, 0))

const authScopeLine = computed(() => {
  const scope = props.card.shareScope
  if (!scope) return '授权范围：未设置'
  if (scope.scopeMode === 'PUBLIC') return '授权范围：公开（全公司可用）'
  return `授权对象 ${scope.grantTotal} 人 · ${scope.summary || '未设置'}`
})

function onAction(action: AssistantAction): void {
  emit('action', action, props.card)
}

/** 整卡点击进详情；按钮、复选框区域除外 */
function onCardClick(event: MouseEvent): void {
  if ((event.target as HTMLElement).closest('.card-check, .card-actions')) return
  emit('action', 'detail', props.card)
}
</script>

<template>
  <div
    class="assistant-card"
    :class="{ selected, 'has-check': selectable, 'is-auth': isAuthView }"
    @click="onCardClick"
  >
    <el-checkbox
      v-if="selectable"
      class="card-check"
      :model-value="selected"
      :disabled="!canShare"
      @update:model-value="(v: boolean | string | number) => emit('update:selected', !!v)"
    />

    <div class="card-top">
      <AssistantAvatar
        :type="card.avatarType"
        :char="card.avatarChar"
        :url="card.avatarUrl"
        :color="card.avatarColor"
        :name="card.name"
        :seed="card.assistantId"
        :size="48"
      />
      <div class="card-name-wrap">
        <div class="card-name">
          <span class="name-text">{{ card.name }}</span>
          <!-- 状态角标：平台预置 / 已共享（我创建）/ 已订阅（别人创建）三类互斥 -->
          <StatusTag v-if="card.source === 'platform'" status="platform" />
          <StatusTag v-else-if="card.source === 'shared'" :status="card.subscribeStatus" />
          <StatusTag v-else-if="card.shareStatus" :status="card.shareStatus" />
          <span class="ver-tag">{{ card.version }}</span>
        </div>
        <div class="card-tags">
          <span v-for="t in visibleTags" :key="t" class="mini-tag">{{ t }}</span>
          <span
            v-if="moreTagCount"
            class="mini-tag tag-more"
            :title="`共 ${card.tags.length} 个标签：${card.tags.join('、')}`"
          >
            +{{ moreTagCount }}
          </span>
        </div>
      </div>
    </div>

    <div class="card-desc">{{ card.descriptionTruncated }}</div>

    <div v-if="isAuthView" class="auth-scope-line">{{ authScopeLine }}</div>

    <div v-if="card.shareStatus === 'rejected' && scope === 'mine'" class="reject-bar">
      <span class="reject-text">拒绝原因：{{ card.rejectReason || '管理员未填写拒绝原因' }}</span>
    </div>

    <div class="card-actions">
      <template v-if="isAuthView">
        <button class="act-btn act-btn-text" @click.stop="emit('action', 'detail', card)">详情</button>
        <button class="act-btn act-btn-primary" @click.stop="onAction('shareScope')">调整范围</button>
      </template>
      <template v-else>
        <button
          v-for="a in visibleActions"
          :key="a"
          class="act-btn act-btn-primary"
          @click.stop="onAction(a)"
        >
          {{ ACTION_LABEL[a] }}
        </button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.assistant-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 150px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid var(--at-border);
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.16s, border-color 0.16s, box-shadow 0.16s, transform 0.16s;
}

.assistant-card > * {
  flex-shrink: 0;
}

.assistant-card:hover {
  background: #f5f9ff;
  border-color: rgba(54, 133, 242, 0.35);
  box-shadow: 0 6px 18px rgba(20, 60, 150, 0.12);
  transform: translateY(-1px);
  z-index: 2;
}

.assistant-card.selected {
  border-color: var(--at-brand);
  box-shadow: 0 0 0 1px var(--at-brand) inset;
}

.card-check {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 3;
}

.assistant-card.has-check .card-top {
  padding-left: 22px;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-name-wrap {
  min-width: 0;
  flex: 1;
}

.card-name {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  line-height: 20px;
}

.name-text {
  font-size: 14px;
  font-weight: 600;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ver-tag {
  color: var(--at-text-weak);
  font-size: 11px;
  font-family: var(--font-mono, monospace);
  white-space: nowrap;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
  min-height: 18px;
}

.mini-tag {
  padding: 2px 10px;
  background: #fff;
  border: 1px solid var(--at-border);
  border-radius: 999px;
  color: var(--at-text-sub);
  font-size: 11px;
  line-height: 16px;
  white-space: nowrap;
}

.mini-tag.tag-more {
  color: var(--at-text-weak);
}

.card-desc {
  font-size: 12px;
  line-height: 20px;
  color: var(--at-text-sub);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 40px;
}

.auth-scope-line {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  font-size: 11px;
  color: var(--at-text-weak);
  background: #f4f8fe;
  border-radius: 4px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.reject-bar {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 6px 8px;
  background: #fff6f5;
  border-radius: 4px;
  font-size: 12px;
  line-height: 18px;
  color: #d92d20;
}

.reject-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 卡片操作：召唤按钮默认常驻展示
 * 尺寸对齐 prototype .expert-actions：按钮等分占满卡片宽度、30px 高、12px 字号 */
.card-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  width: 100%;
  margin-top: auto;
  min-height: 34px;
  padding-top: 4px;
}

/* 卡片按钮：对齐 prototype .expert-card .expert-actions .btn */
.act-btn {
  flex: 1 1 auto;
  min-width: 64px;
  height: 30px;
  padding: 0 8px;
  font-family: inherit;
  font-size: 12px;
  font-weight: 400;
  line-height: 1;
  border: 1px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  transition: background-color 0.2s ease, box-shadow 0.2s ease,
    border-color 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

/* 召唤按钮：默认浅色底 + 品牌色文字/描边，悬停转为蓝色渐变并上浮 */
.act-btn-primary {
  color: var(--at-brand);
  background: #f4f8ff;
  border-color: rgba(54, 133, 242, 0.32);
  box-shadow: none;
}

.act-btn-primary:hover {
  color: #fff;
  background: linear-gradient(135deg, #3685f2, #1e63d6);
  border-color: rgba(54, 133, 242, 0.65);
  box-shadow: 0 6px 14px rgba(54, 133, 242, 0.42);
  transform: translateY(-2px);
}

.act-btn-primary:active {
  transform: translateY(0);
  box-shadow: 0 2px 6px rgba(54, 133, 242, 0.3);
}

.act-btn-text {
  color: #646a73;
  background: #fff;
  border-color: var(--at-border);
}

.act-btn-text:hover {
  color: var(--at-brand);
  border-color: var(--at-brand);
}
</style>
