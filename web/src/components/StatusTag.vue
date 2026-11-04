<script setup lang="ts">
import { computed } from 'vue'
import type { ShareStatus, SubscribeStatus } from '@/types/assistant'

/** 共享状态角标（需求 4.0：未共享 / 待审批 / 已共享 / 已拒绝） */
const props = defineProps<{ status: ShareStatus | SubscribeStatus | null }>()

const MAP: Record<string, { text: string; cls: string }> = {
  unshared: { text: '未共享', cls: 'is-default' },
  pending: { text: '待审批', cls: 'is-warning' },
  approved: { text: '已共享', cls: 'is-success' },
  rejected: { text: '已拒绝', cls: 'is-error' },
  subscribed: { text: '已订阅', cls: 'is-success' },
  removed: { text: '已移除', cls: 'is-default' }
}

const view = computed(() => (props.status ? MAP[props.status] : null))
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
