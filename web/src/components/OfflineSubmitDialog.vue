<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { submitOfflineApi } from '@/api'
import type { AssistantCard } from '@/types/assistant'
import { ApiError } from '@/types/api'

/** 申请下架：对齐 prototype requestOffline —— 填写原因后提交管理员审批 */
const props = defineProps<{ modelValue: boolean; card: AssistantCard | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; submitted: [] }>()

const reason = ref('')
const saving = ref(false)

const canSubmit = computed(() => reason.value.trim().length > 0)

watch(
  () => props.modelValue,
  (open) => {
    if (open) reason.value = ''
  }
)

async function submit(): Promise<void> {
  if (!props.card) return
  const text = reason.value.trim()
  if (!text) {
    ElMessage.error('请填写下架原因')
    return
  }
  saving.value = true
  try {
    await submitOfflineApi(props.card.assistantId, text)
    ElMessage.success('已提交下架申请，等待管理员审批')
    emit('update:modelValue', false)
    emit('submitted')
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '提交失败，请稍后重试')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="`申请下架 · ${card?.name ?? ''}`"
    width="560px"
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <div class="offline-body">
      <div class="notice-bar">
        已共享的助理不能直接删除。提交下架申请后，管理员审批通过即从授权对象的助理库中移除。
      </div>
      <div class="form-item">
        <label class="form-label required">下架原因</label>
        <el-input
          v-model="reason"
          type="textarea"
          :rows="4"
          maxlength="200"
          show-word-limit
          placeholder="请说明下架原因，例如：规则调整、内容过期、能力合并等（1-200 字）"
        />
      </div>
      <div class="form-hint">
        当前版本：{{ card?.version ?? 'v1.0' }} · 授权对象 {{ card?.authorizedCount ?? 0 }} 个
      </div>
    </div>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="danger" :disabled="!canSubmit" :loading="saving" @click="submit">
        提交下架申请
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.offline-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.notice-bar {
  padding: 8px 12px;
  background: #fff8e6;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: #8a5a00;
}

.form-label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--at-text);
}

.form-label.required::before {
  content: '*';
  margin-right: 4px;
  color: var(--at-danger);
}

.form-hint {
  font-size: 12px;
  color: var(--at-text-weak);
}
</style>
