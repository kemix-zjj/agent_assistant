<script setup lang="ts">
import { computed } from 'vue'
import type { ShareStatus, SubscribeStatus, ApproveSubType } from '@/types/assistant'

/**
 * 共享状态角标（需求 4.0 共享状态与文案统一）
 * - 「我的助理」范围：审批中展示「审批中 · {子类}」，已拒绝展示「已拒绝 · {子类}」
 * - 「全部」范围：不传子类时按平台内置 / 已共享 / 已订阅三种状态展示
 */
const props = defineProps<{
  status: ShareStatus | SubscribeStatus | 'platform' | null
  pendingType?: ApproveSubType | null
  rejectType?: ApproveSubType | null
}>()

const SUB_TEXT: Record<ApproveSubType, string> = {
  share: '共享审批',
  change: '调整审批',
  scope: '授权审批',
  offline: '下架审批'
}

const MAP: Record<string, { text: string; cls: string }> = {
  platform: { text: '平台内置', cls: 'is-default' },
  unshared: { text: '未共享', cls: 'is-default' },
  approved: { text: '已共享', cls: 'is-success' },
  offline: { text: '已下架', cls: 'is-default' },
  subscribed: { text: '已订阅', cls: 'is-success' },
  removed: { text: '已移除', cls: 'is-default' }
}

const view = computed(() => {
  const status = props.status
  if (!status) return null
  if (status === 'pending') {
    const sub = props.pendingType ?? 'share'
    return { text: `审批中 · ${SUB_TEXT[sub]}`, cls: 'is-warning' }
  }
  if (status === 'rejected') {
    const sub = props.rejectType ?? 'share'
    return { text: `已拒绝 · ${SUB_TEXT[sub]}`, cls: 'is-error' }
  }
  return MAP[status] ?? null
})
</script>

<template>
  <span v-if="view" class="status-tag" :class="view.cls">{{ view.text }}</span>
</template>

<style scoped>
.status-tag {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 6px;
  border-radius: 3px;
  font-size: 12px;
  line-height: 1;
  font-weight: 400;
  white-space: nowrap;
}

.is-default {
  background: #f2f3f5;
  color: #646a73;
}

.is-warning {
  background: #fff3e8;
  color: #d25f00;
}

.is-success {
  background: #e8f8f2;
  color: #00875a;
}

.is-error {
  background: #ffece8;
  color: #d92d20;
}
</style>
