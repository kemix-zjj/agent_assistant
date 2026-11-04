<script setup lang="ts">
/**
 * 添加助理：创建方式选择弹窗
 * 对齐原型 openCreateChooser —— 手动创建（推荐）/ 已有接入 / 自然语言创建（研发中，禁用）
 */
defineProps<{ modelValue: boolean }>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  select: [mode: 'manual' | 'thirdparty']
}>()

function choose(mode: 'manual' | 'thirdparty'): void {
  emit('select', mode)
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="添加助理"
    width="720px"
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <div class="create-opts">
      <div class="create-opt" @click="choose('manual')">
        <div class="create-opt-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
        </div>
        <div class="create-opt-body">
          <div class="create-opt-title">
            手动创建<span class="create-opt-flag">推荐</span>
          </div>
          <div class="create-opt-desc">通过表单逐步配置助理：基础信息 → 能力配置 → 共享设置</div>
        </div>
        <span class="create-opt-arrow">›</span>
      </div>

      <div class="create-opt" @click="choose('thirdparty')">
        <div class="create-opt-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
        </div>
        <div class="create-opt-body">
          <div class="create-opt-title">已有接入</div>
          <div class="create-opt-desc">接入已在第三方平台运行的助理，如飞书、钉钉、企业微信、自定义 API</div>
        </div>
        <span class="create-opt-arrow">›</span>
      </div>

      <div class="create-opt disabled">
        <div class="create-opt-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
          </svg>
        </div>
        <div class="create-opt-body">
          <div class="create-opt-title">
            自然语言创建<span class="create-opt-flag gray">研发中</span>
          </div>
          <div class="create-opt-desc">用一句话描述你需要的助理，系统自动生成提示词与能力配置</div>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.create-opts {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.create-opt {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid var(--at-border);
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.create-opt:hover {
  border-color: var(--at-brand);
  background: #eef4ff;
}

.create-opt-icon {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #eef4ff;
  color: var(--at-brand);
  border-radius: 4px;
}

.create-opt-icon svg {
  width: 18px;
  height: 18px;
}

.create-opt-body {
  flex: 1;
  min-width: 0;
}

.create-opt-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--at-text);
}

.create-opt-desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--at-text-sub);
}

.create-opt-flag {
  padding: 0 6px;
  font-size: 11px;
  font-weight: 400;
  line-height: 16px;
  color: #fff;
  background: var(--at-brand);
  border-radius: 3px;
}

.create-opt-flag.gray {
  background: #f2f3f5;
  color: var(--at-text-sub);
}

.create-opt-arrow {
  color: var(--at-text-weak);
  font-size: 18px;
  line-height: 1;
}

.create-opt.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.create-opt.disabled:hover {
  border-color: var(--at-border);
  background: #fff;
}
</style>
