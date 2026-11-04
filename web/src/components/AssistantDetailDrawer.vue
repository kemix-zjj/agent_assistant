<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AssistantAvatar from './AssistantAvatar.vue'
import StatusTag from './StatusTag.vue'
import { getAssistantDetail } from '@/api'
import type { AssistantDetail } from '@/types/assistant'
import { ApiError } from '@/types/api'

/** 助理详情：基础信息 / 能力组成 / 授权范围 / 版本记录（被授权方视角隐藏提示词与能力组成） */
const props = defineProps<{ modelValue: boolean; assistantId: number | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const detail = ref<(AssistantDetail & { categoryName?: string }) | null>(null)
const loading = ref(false)
const activeTab = ref('basic')

const ACTION_NAME: Record<string, string> = {
  create: '创建',
  update: '编辑更新',
  share_submit: '提交共享',
  share_approve: '审批通过',
  share_reject: '审批拒绝',
  scope_change: '授权范围变更',
  delete: '删除'
}

watch(
  () => props.modelValue,
  async (open) => {
    if (!open || !props.assistantId) return
    loading.value = true
    activeTab.value = 'basic'
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
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    size="640px"
    :close-on-click-modal="false"
    title="助理详情"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <div v-loading="loading" class="detail-body">
      <template v-if="detail">
        <div class="detail-head">
          <AssistantAvatar
            :type="detail.avatarType"
            :char="detail.avatarChar"
            :url="detail.avatarUrl"
            :color="detail.avatarColor"
            :name="detail.name"
            :size="52"
          />
          <div class="head-info">
            <div class="head-name">
              {{ detail.name }}
              <StatusTag v-if="detail.shareStatus" :status="detail.shareStatus" />
              <span class="ver-tag">{{ detail.version }}</span>
            </div>
            <div class="head-meta">
              {{ detail.categoryName }}
              <span v-if="detail.ownerName"> · 创建人 {{ detail.ownerName }}</span>
              <span v-if="detail.ownerDeptName"> · {{ detail.ownerDeptName }}</span>
            </div>
            <div class="head-tags">
              <span v-for="t in detail.tags" :key="t" class="mini-tag">{{ t }}</span>
            </div>
          </div>
        </div>

        <el-tabs v-model="activeTab">
          <el-tab-pane label="基础信息" name="basic">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="描述">{{ detail.description }}</el-descriptions-item>
              <el-descriptions-item label="所属分类">{{ detail.categoryName }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ detail.createdAt }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ detail.updatedAt }}</el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>

          <el-tab-pane label="能力组成" name="ability">
            <div v-if="detail.prompt === null" class="no-permission">
              共享助理由创建人维护，被授权方仅可召唤使用，不可查看配置。
            </div>
            <template v-else>
              <div class="section">
                <div class="section-title">提示词</div>
                <pre class="prompt-view">{{ detail.prompt }}</pre>
              </div>
              <div class="section">
                <div class="section-title">SKILL（{{ detail.skills?.length ?? 0 }}）</div>
                <div v-if="detail.skills?.length" class="chip-list">
                  <el-tag v-for="s in detail.skills" :key="s.id" type="info" size="small">{{ s.name }}</el-tag>
                </div>
                <div v-else class="empty-text">未配置</div>
              </div>
              <div class="section">
                <div class="section-title">MCP（{{ detail.mcps?.length ?? 0 }}）</div>
                <div v-if="detail.mcps?.length" class="chip-list">
                  <el-tag v-for="m in detail.mcps" :key="m.id" type="info" size="small">{{ m.name }}</el-tag>
                </div>
                <div v-else class="empty-text">未配置</div>
              </div>
              <div class="section">
                <div class="section-title">知识库（{{ detail.knowledgeBases?.length ?? 0 }}）</div>
                <div v-if="detail.knowledgeBases?.length" class="chip-list">
                  <el-tag v-for="k in detail.knowledgeBases" :key="k.id" type="info" size="small">{{ k.name }}</el-tag>
                </div>
                <div v-else class="empty-text">未配置</div>
              </div>
              <div class="section">
                <div class="section-title">召唤快速问题（{{ detail.quickQuestions.length }}）</div>
                <div v-if="detail.quickQuestions.length" class="qq-list">
                  <div v-for="q in detail.quickQuestions" :key="q" class="qq-item">{{ q }}</div>
                </div>
                <div v-else class="empty-text">未配置</div>
              </div>
            </template>
          </el-tab-pane>

          <el-tab-pane label="授权范围" name="scope">
            <template v-if="detail.shareScope">
              <div class="scope-summary">
                <span class="scope-mode-tag">{{ detail.shareScope.scopeMode === 'PUBLIC' ? '公开' : '范围授权' }}</span>
                <span>{{ detail.shareScope.summary }}</span>
                <span class="grant-total">授权 {{ detail.shareScope.grantTotal }} 人</span>
              </div>
              <div v-if="detail.shareScope.scopeMode === 'RANGE'" class="chip-list">
                <el-tag v-for="o in detail.shareScope.orgs" :key="o.id" size="small" type="info">组织 · {{ o.name }}</el-tag>
                <el-tag v-for="r in detail.shareScope.roles" :key="r.id" size="small" type="info">角色 · {{ r.name }}</el-tag>
                <el-tag v-for="p in detail.shareScope.positions" :key="p.id" size="small" type="info">岗位 · {{ p.name }}</el-tag>
                <el-tag v-for="u in detail.shareScope.users" :key="u.id" size="small" type="info">{{ u.name }}</el-tag>
              </div>
            </template>
            <div v-else class="empty-text">该助理尚未共享</div>
          </el-tab-pane>

          <el-tab-pane label="版本记录" name="history">
            <el-timeline v-if="detail.versionHistory.length">
              <el-timeline-item
                v-for="h in detail.versionHistory"
                :key="`${h.version}-${h.createdAt}`"
                :timestamp="h.createdAt"
                placement="top"
              >
                <div class="history-item">
                  <span class="history-ver">{{ h.version }}</span>
                  <span class="history-action">{{ ACTION_NAME[h.action] ?? h.actionName }}</span>
                  <span class="history-operator">{{ h.operatorName }}</span>
                </div>
                <div v-if="h.remark" class="history-remark">{{ h.remark }}</div>
              </el-timeline-item>
            </el-timeline>
            <div v-else class="empty-text">暂无版本记录</div>
          </el-tab-pane>
        </el-tabs>
      </template>
    </div>
  </el-drawer>
</template>

<style scoped>
.detail-body {
  min-height: 300px;
}

.detail-head {
  display: flex;
  gap: 14px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--at-border);
  margin-bottom: 8px;
}

.head-info {
  min-width: 0;
}

.head-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}

.ver-tag {
  font-size: 11px;
  color: var(--at-text-weak);
  font-weight: 400;
}

.head-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--at-text-sub);
}

.head-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.mini-tag {
  padding: 0 6px;
  background: #f2f3f5;
  border-radius: 3px;
  color: var(--at-text-sub);
  font-size: 11px;
  line-height: 18px;
}

.section {
  margin-bottom: 18px;
}

.section-title {
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
}

.prompt-view {
  margin: 0;
  padding: 10px 12px;
  background: #f7f8fa;
  border-radius: 4px;
  font-family: inherit;
  font-size: 12px;
  line-height: 20px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--at-text-sub);
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.qq-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.qq-item {
  padding: 6px 10px;
  background: #f7f8fa;
  border-radius: 4px;
  font-size: 13px;
}

.empty-text {
  font-size: 12px;
  color: var(--at-text-weak);
  padding: 6px 0;
}

.no-permission {
  padding: 40px 0;
  text-align: center;
  color: var(--at-text-weak);
  font-size: 13px;
}

.scope-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 13px;
}

.scope-mode-tag {
  padding: 1px 6px;
  border-radius: 3px;
  background: #eef4ff;
  color: var(--at-brand);
  font-size: 12px;
}

.grant-total {
  margin-left: auto;
  font-size: 12px;
  color: var(--at-text-weak);
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.history-ver {
  font-weight: 600;
}

.history-action {
  color: var(--at-text-sub);
}

.history-operator {
  color: var(--at-text-weak);
  font-size: 12px;
}

.history-remark {
  margin-top: 4px;
  font-size: 12px;
  color: var(--at-text-weak);
}
</style>
