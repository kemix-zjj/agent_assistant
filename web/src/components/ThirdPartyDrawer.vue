<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

/**
 * 已有接入：接入第三方助理（对齐原型 openThirdParty）
 * 本期仅做表单闭环演示，接入后助理由第三方平台运行，本平台负责调用与授权管理。
 */
defineProps<{ modelValue: boolean }>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const PLATFORMS = ['飞书智能伙伴', '钉钉 AI 助理', '企业微信智能助手', '自定义 API']

const form = reactive({
  platform: PLATFORMS[0],
  name: '',
  endpoint: '',
  appId: '',
  secret: '',
  description: ''
})

const testing = ref(false)
const connected = ref(false)
const submitting = ref(false)

watch(
  () => form.name,
  () => {
    connected.value = false
  }
)

function testConnection(): void {
  if (!form.endpoint.trim()) {
    ElMessage.error('请先填写接入地址')
    return
  }
  if (!form.appId.trim() || !form.secret.trim()) {
    ElMessage.error('请填写 AppID 与 AppSecret')
    return
  }
  testing.value = true
  setTimeout(() => {
    testing.value = false
    connected.value = true
    ElMessage.success('连接测试通过')
  }, 800)
}

function submit(): void {
  if (!form.name.trim()) {
    ElMessage.error('请填写助理名称')
    return
  }
  if (form.name.trim().length < 2 || form.name.trim().length > 20) {
    ElMessage.error('助理名称需为 2-20 个字符')
    return
  }
  if (!form.endpoint.trim()) {
    ElMessage.error('请填写接入地址')
    return
  }
  submitting.value = true
  setTimeout(() => {
    submitting.value = false
    ElMessage.success(`已提交接入「${form.name}」，等待平台校验`)
    emit('saved')
    emit('update:modelValue', false)
  }, 400)
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="已有接入 · 接入第三方助理"
    size="640px"
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <div class="tp-body">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="接入后助理仍由第三方平台运行，本平台负责调用与授权管理。"
      />

      <div class="form-item">
        <label class="form-label required">来源平台</label>
        <el-select v-model="form.platform" class="full">
          <el-option v-for="p in PLATFORMS" :key="p" :label="p" :value="p" />
        </el-select>
      </div>

      <div class="form-item">
        <label class="form-label required">助理名称</label>
        <el-input v-model="form.name" maxlength="20" placeholder="与第三方平台展示名称一致，2-20 个字符" />
      </div>

      <div class="form-item">
        <label class="form-label required">接入地址</label>
        <el-input v-model="form.endpoint" placeholder="https://open.example.com/assistant/api" />
      </div>

      <div class="form-row">
        <div class="form-item">
          <label class="form-label required">AppID</label>
          <el-input v-model="form.appId" placeholder="平台应用的 AppID" />
        </div>
        <div class="form-item">
          <label class="form-label required">AppSecret</label>
          <el-input v-model="form.secret" type="password" show-password placeholder="平台应用的 AppSecret" />
        </div>
      </div>

      <div class="form-item">
        <label class="form-label">能力说明</label>
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          maxlength="200"
          placeholder="简述该助理可解决的问题，用于助理卡片展示"
        />
      </div>

      <div class="tp-test">
        <span class="form-hint">{{ connected ? '连接正常，可提交接入' : '填写完成后可先测试连接' }}</span>
        <el-button size="small" :loading="testing" @click="testConnection">测试连接</el-button>
      </div>
    </div>

    <template #footer>
      <div class="drawer-footer">
        <el-button @click="emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">提交接入</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.tp-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-row > .form-item {
  flex: 1;
  min-width: 0;
}

.form-item {
  display: flex;
  flex-direction: column;
}

.form-label {
  font-size: 13px;
  color: var(--at-text);
  margin-bottom: 6px;
}

.form-label.required::before {
  content: '*';
  color: #f5483b;
  margin-right: 3px;
}

.form-hint {
  font-size: 12px;
  color: var(--at-text-weak);
}

.full {
  width: 100%;
}

.tp-test {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 8px;
  border-top: 1px solid #ebedf0;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
