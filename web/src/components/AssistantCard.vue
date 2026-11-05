<script setup lang="ts">
import { computed } from 'vue'
import AssistantAvatar from './AssistantAvatar.vue'
import StatusTag from './StatusTag.vue'
import { useUserStore } from '@/stores/user'
import type { AssistantCard, AssistantAction } from '@/types/assistant'

/** 助理卡片：列表页三范围共用，按钮由后端 actions 驱动 */
const props = defineProps<{
  card: AssistantCard
  scope?: 'all' | 'mine' | 'shared'
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
  remove: '移除',
  resubscribe: '重新订阅'
}

/** 需求 F-EXP-002：平台预置助理的「授权范围」仅公司管理员可见 */
const visibleActions = computed(() =>
  (props.card.actions ?? []).filter((a) => {
    if (a === 'edit' || a === 'delete' || a === 'share' || a === 'resubmit') {
      return props.scope === 'mine'
    }
    if (a === 'shareScope') {
      if (props.card.source === 'platform') return isAdmin.value
      return props.scope !== 'shared'
    }
    return true
  })
)

const userStore = useUserStore()
const isAdmin = computed(() => userStore.isAdmin)

const canShare = computed(
  () =>
    props.scope === 'mine' &&
    props.card.source !== 'shared' &&
    (props.card.shareStatus === 'unshared' || props.card.shareStatus === 'rejected')
)

const ownerLine = computed(() => {
  if (props.card.source === 'shared' && props.card.sharedFrom) {
    const dept = props.card.sharedFrom.ownerDeptName.split(' · ').pop()
    return `共享自 ${props.card.sharedFrom.ownerName}${dept ? ` · ${dept}` : ''}`
  }
  if (props.card.source === 'platform') return `平台预置 · ${props.card.categoryName}`
  return props.card.ownerName ?? ''
})

function onAction(action: AssistantAction): void {
  emit('action', action, props.card)
}
</script>

<template>
  <div class="assistant-card" :class="{ selected, 'has-check': selectable }">
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
        :size="36"
      />
      <div class="card-name-wrap">
        <div class="card-name" @click="emit('action', 'detail', card)">
          <span class="name-text">{{ card.name }}</span>
          <StatusTag v-if="card.source === 'shared'" :status="card.subscribeStatus" />
          <StatusTag v-else-if="card.shareStatus" :status="card.shareStatus" />
          <span v-if="card.source === 'shared'" class="shared-flag">共享</span>
          <span class="ver-tag">{{ card.version }}</span>
        </div>
        <div class="card-tags">
          <span v-for="t in card.tags.slice(0, 3)" :key="t" class="mini-tag">{{ t }}</span>
        </div>
      </div>
    </div>

    <div class="card-desc">{{ card.descriptionTruncated }}</div>

    <div v-if="card.shareStatus === 'rejected'" class="reject-bar" :class="{ expanded: expandedReject }">
      <span class="reject-text">拒绝原因：{{ card.rejectReason || '管理员未填写拒绝原因' }}</span>
      <span class="reject-toggle" @click="emit('action', 'toggleReject', card)">
        {{ expandedReject ? '收起' : '展开' }}
      </span>
    </div>

    <div class="card-foot">
      <span class="card-owner">{{ ownerLine }}</span>
      <span class="card-actions">
        <el-button
          v-for="a in visibleActions"
          :key="a"
          link
          type="primary"
          size="small"
          @click="onAction(a)"
        >
          {{ ACTION_LABEL[a] }}
        </el-button>
        <el-button v-if="card.source !== 'shared'" link size="small" @click="emit('action', 'detail', card)">
          详情
        </el-button>
      </span>
    </div>
  </div>
</template>

<style scoped>
.assistant-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid var(--at-border);
  border-radius: 6px;
  transition: box-shadow 0.15s, border-color 0.15s;
}

.assistant-card:hover {
  border-color: #c8d6f0;
  box-shadow: 0 2px 10px rgba(31, 35, 41, 0.06);
}

.assistant-card.selected {
  border-color: var(--at-brand);
  box-shadow: 0 0 0 1px var(--at-brand) inset;
}

.card-check {
  position: absolute;
  top: 10px;
  left: 10px;
}

.assistant-card.has-check .card-top {
  padding-left: 22px;
}

.card-top {
  display: flex;
  align-items: flex-start;
  gap: 10px;
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
  cursor: pointer;
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

.name-text:hover {
  color: var(--at-brand);
}

.shared-flag {
  padding: 0 5px;
  border: 1px solid #c8d6f0;
  border-radius: 3px;
  color: var(--at-brand);
  font-size: 11px;
  line-height: 16px;
}

.ver-tag {
  color: var(--at-text-weak);
  font-size: 11px;
  font-family: var(--font-mono, monospace);
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
  min-height: 18px;
}

.mini-tag {
  padding: 0 6px;
  background: #f2f3f5;
  border-radius: 3px;
  color: var(--at-text-sub);
  font-size: 11px;
  line-height: 18px;
}

.card-desc {
  font-size: 12px;
  line-height: 20px;
  color: var(--at-text-sub);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 40px;
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

.reject-bar:not(.expanded) .reject-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.reject-text {
  flex: 1;
}

.reject-toggle {
  flex: 0 0 auto;
  cursor: pointer;
  color: var(--at-brand);
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #f2f3f5;
}

.card-owner {
  font-size: 12px;
  color: var(--at-text-weak);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-actions {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
}

.card-actions :deep(.el-button + .el-button) {
  margin-left: 8px;
}
</style>
