<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import ScopePicker from './ScopePicker.vue'
import { submitShareApi } from '@/api'
import type { AssistantCard } from '@/types/assistant'
import type { ScopePayload } from '@/types/scope'
import { ApiError } from '@/types/api'

/** 共享提交弹窗：单条重新提交与批量勾选提交共用（F-SHR-001 / F-SHR-003） */
const props = defineProps<{ modelValue: boolean; assistants: AssistantCard[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; submitted: [] }>()

const scope = ref<ScopePayload>({ scopeMode: 'RANGE', orgs: [], roles: [], positions: [], users: [] })
const changeNote = ref('')
const submitting = ref(false)
const pickerRef = ref<InstanceType<typeof ScopePicker>>()

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      scope.value = { scopeMode: 'RANGE', orgs: [], roles: [], positions: [], users: [] }
      changeNote.value = ''
    }
  }
)

const canSubmit = computed(() => {
  if (!props.assistants.length) return false
  if (scope.value.scopeMode === 'PUBLIC') return true
  return (
    scope.value.orgs.length > 0 ||
    scope.value.roles.length > 0 ||
    scope.value.positions.length > 0 ||
    scope.value.users.length > 0
  )
})

async function submit(): Promise<void> {
  if (!canSubmit.value) {
    ElMessage.warning('请至少选择一个组织或人员')
    return
  }
  submitting.value = true
  try {
    await submitShareApi({
      assistantIds: props.assistants.map((e) => e.assistantId),
      scope: scope.value,
      changeNote: changeNote.value.trim() || undefined
    })
    ElMessage.success('已提交审批，等待管理员处理')
    emit('submitted')
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="提交共享申请"
    width="640px"
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <div class="share-body">
      <div class="share-section">
        <div class="section-label">已选助理（{{ assistants.length }}）</div>
        <div class="assistant-chips">
          <span v-for="e in assistants.slice(0, 6)" :key="e.assistantId" class="assistant-chip">
            {{ e.name }}
          </span>
          <span v-if="assistants.length > 6" class="assistant-chip more">+{{ assistants.length - 6 }}</span>
        </div>
      </div>

      <div class="share-section">
        <div class="section-label">共享范围</div>
        <ScopePicker
          ref="pickerRef"
          v-model="scope"
          show-limits
          tip="按组织、岗位、角色、人员批量选择，来源维度会把人展开带进「按人员」；最终共享对象是人员。上限：组织 50 个节点、岗位/角色各 50 项、人员 200 人。"
        />
      </div>

      <div class="share-section">
        <div class="section-label">申请说明（选填）</div>
        <el-input
          v-model="changeNote"
          type="textarea"
          :rows="2"
          maxlength="200"
          show-word-limit
          placeholder="简要说明共享用途，便于管理员审批"
        />
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :disabled="!canSubmit" :loading="submitting" @click="submit">提交</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.share-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-height: 64vh;
  overflow-y: auto;
  padding-right: 4px;
}

.section-label {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 8px;
}

.assistant-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.assistant-chip {
  padding: 3px 10px;
  background: #eef4ff;
  border-radius: 4px;
  color: var(--at-brand);
  font-size: 12px;
}

.assistant-chip.more {
  background: #f2f3f5;
  color: var(--at-text-sub);
}
</style>
