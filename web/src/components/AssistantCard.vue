<script setup lang="ts">
import { computed } from 'vue'
import AssistantAvatar from './AssistantAvatar.vue'
import StatusTag from './StatusTag.vue'
import { displayVersion } from '@/api/mock'
import type { AssistantCard, AssistantAction } from '@/types/assistant'

/** 助理卡片：列表三范围共用，按钮由后端 actions 驱动
 * 整卡点击进详情；召唤按钮常驻展示，悬停有渐变、描边与轻微上浮动效；标签最多 2 个其余 +N。
 */
const props = defineProps<{
  card: AssistantCard
  scope?: 'all' | 'mine' | 'shared'
  selectable?: boolean
  selected?: boolean
}>()

const emit = defineEmits<{
  action: [action: AssistantAction | 'detail', card: AssistantCard]
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

/** 卡片只展示召唤入口，其余操作收进详情抽屉 */
const visibleActions = computed<AssistantAction[]>(() =>
  (props.card.actions ?? []).filter((a) => a === 'summon')
)

/** 批量共享只允许勾选「本质未共享」的助理（未共享；共享审批被拒需走详情重新提交） */
const canShare = computed(
  () =>
    props.scope === 'mine' &&
    props.card.source !== 'shared' &&
    props.card.shareStatus === 'unshared'
)

/** 标签：最多展示 2 个，其余以 +N 收拢（完整标签见详情） */
const visibleTags = computed(() => props.card.tags.slice(0, 2))
const moreTagCount = computed(() => Math.max(props.card.tags.length - 2, 0))

/** 角标口径：全部页签不展开审批 / 拒绝子类，明细子类只在「我的助理」展示 */
const showSubType = computed(() => props.scope === 'mine')

const versionText = computed(() => displayVersion(props.card.version))

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
    :class="{ selected, 'has-check': canShare }"
    @click="onCardClick"
  >
    <el-checkbox
      v-if="canShare"
      class="card-check"
      :model-value="selected"
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
          <!-- 状态角标：平台内置 / 已共享（我创建）/ 已订阅（别人创建）三类互斥 -->
          <StatusTag v-if="card.source === 'platform'" status="platform" />
          <StatusTag v-else-if="card.source === 'shared'" :status="card.subscribeStatus" />
          <StatusTag
            v-else-if="card.shareStatus"
            :status="card.shareStatus"
            :pending-type="showSubType ? card.pendingType : null"
            :reject-type="showSubType ? card.rejectType : null"
          />
          <span class="ver-tag">{{ versionText }}</span>
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

    <div class="card-actions">
      <button
        v-for="a in visibleActions"
        :key="a"
        class="act-btn act-btn-primary"
        @click.stop="onAction(a)"
      >
        {{ ACTION_LABEL[a] }}
      </button>
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
</style>
