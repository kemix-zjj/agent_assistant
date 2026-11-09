<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import ScopePicker from './ScopePicker.vue'
import {
  aiGenerate,
  createCategory,
  createAssistantApi,
  getAssistantDetail,
  getKnowledgeBases,
  getMcps,
  getSkills,
  submitShareApi,
  updateAssistantApi,
  uploadAvatar
} from '@/api'
import type {
  CategoryItem,
  AssistantUpsertPayload,
  KnowledgeBaseItem,
  McpItem,
  ResourceMarket,
  SkillItem
} from '@/types/assistant'
import type { ScopePayload } from '@/types/scope'
import { ApiError } from '@/types/api'
import { PRESET_AVATARS, resolvePresetKey, presetColor } from '@/utils/avatar'

/**
 * 手动创建 / 编辑助理：三步向导（对齐原型 openWizard）
 * 步骤 1 基础信息 → 步骤 2 能力配置 → 步骤 3 共享设置（编辑时为「确认提交」）
 */
const props = defineProps<{
  modelValue: boolean
  categories: CategoryItem[]
  assistantId?: number | null
  /** 已共享助理编辑时的授权对象数，用于变更影响提示 */
  affectedGrantCount?: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
  'create-category': [item: CategoryItem]
}>()

const isEdit = computed(() => !!props.assistantId)
const step = ref(1)

const saving = ref(false)
const loading = ref(false)

const draft = reactive({
  name: '',
  avatarType: 'char' as 'char' | 'image',
  avatarChar: 'P1',
  avatarUrl: null as string | null,
  avatarColor: '#3685F2',
  description: '',
  tags: [] as string[],
  categoryId: 0,
  prompt: '',
  skillIds: [] as string[],
  mcpIds: [] as string[],
  knowledgeBaseIds: [] as string[],
  quickQuestions: [] as string[]
})

/** 当前选中的系统默认头像键（P1~P6），编辑历史字符头像时按 ID 稳定回推 */
const presetKey = computed(() => resolvePresetKey(draft.avatarChar, props.assistantId ?? draft.name))

const tagInput = ref('')
const qqInput = ref('')

/** 能力配置：资源页签与市场 */
const resTab = ref<'skill' | 'mcp' | 'kb'>('skill')
const resMarket = ref<ResourceMarket>('internal')
const resKw = ref('')

/** 步骤 3：是否立即申请共享（仅新建） */
const shareMode = ref<'no' | 'yes'>('no')
const shareScope = ref<ScopePayload>({ scopeMode: 'RANGE', orgs: [], roles: [], positions: [], users: [] })


const skills = ref<SkillItem[]>([])
const mcps = ref<McpItem[]>([])
const kbs = ref<KnowledgeBaseItem[]>([])
const resLoading = ref(false)

const aiLoading = ref<Record<string, boolean>>({})
const categoryDialog = ref(false)
const newCategoryName = ref('')

const nameLen = computed(() => draft.name.length)
const promptLen = computed(() => draft.prompt.length)

/** 已共享助理编辑时提示「变更立即生效」（docs/03 §3.4） */
const needReapprove = computed(() => isEdit.value && (props.affectedGrantCount ?? 0) > 0)

/* ---------------- 资源过滤（市场 + 搜索） ---------------- */

const currentCatalog = computed<Array<{ id: string; name: string; sub: string }>>(() => {
  const kw = resKw.value.trim().toLowerCase()
  if (resTab.value === 'skill') {
    return skills.value
      .filter((s) => (s.market ?? 'internal') === resMarket.value)
      .filter((s) => !kw || `${s.name} ${s.desc ?? ''}`.toLowerCase().includes(kw))
      .map((s) => ({ id: s.id, name: s.name, sub: s.desc ?? '' }))
  }
  if (resTab.value === 'mcp') {
    return mcps.value
      .filter((m) => (m.market ?? 'internal') === resMarket.value)
      .filter((m) => !kw || `${m.name} ${m.type ?? ''}`.toLowerCase().includes(kw))
      .map((m) => ({ id: m.id, name: m.name, sub: m.type ?? '' }))
  }
  return kbs.value
    .filter((k) => {
      if (!kw) return true
      if (k.name.toLowerCase().includes(kw)) return true
      return (k.files ?? []).some((f) => f.toLowerCase().includes(kw))
    })
    .map((k) => {
      const hits = kw ? (k.files ?? []).filter((f) => f.toLowerCase().includes(kw)) : []
      const sub = hits.length
        ? `匹配文件：${hits.join('、')}`
        : `${k.documentCount ?? 0} 篇文档 · ${(k.files ?? []).slice(0, 2).join('、')}`
      return { id: k.id, name: k.name, sub }
    })
})

const searchPlaceholder = computed(() => {
  if (resTab.value === 'kb') return '搜索知识库或文件名'
  if (resTab.value === 'mcp') return '搜索连接器名称'
  return '搜索技能名称'
})

function selectedOf(tab: 'skill' | 'mcp' | 'kb'): string[] {
  if (tab === 'skill') return draft.skillIds
  if (tab === 'mcp') return draft.mcpIds
  return draft.knowledgeBaseIds
}

function toggleRes(id: string): void {
  const arr = selectedOf(resTab.value)
  const i = arr.indexOf(id)
  if (i >= 0) {
    arr.splice(i, 1)
    return
  }
  const max = resTab.value === 'kb' ? 20 : 20
  if (arr.length >= max) {
    ElMessage.warning(`每项最多 ${max} 个`)
    return
  }
  arr.push(id)
}

function switchResTab(tab: 'skill' | 'mcp' | 'kb'): void {
  resTab.value = tab
  resKw.value = ''
  resMarket.value = 'internal'
}

/* ---------------- 数据加载 ---------------- */

function resetDraft(): void {
  Object.assign(draft, {
    name: '',
    avatarType: 'char',
    avatarChar: 'P1',
    avatarUrl: null,
    avatarColor: '#3685F2',
    description: '',
    tags: [],
    categoryId: props.categories[0]?.categoryId ?? 0,
    prompt: '',
    skillIds: [],
    mcpIds: [],
    knowledgeBaseIds: [],
    quickQuestions: []
  })
  step.value = 1
  tagInput.value = ''
  qqInput.value = ''
  resTab.value = 'skill'
  resMarket.value = 'internal'
  resKw.value = ''
  shareMode.value = 'no'
  shareScope.value = { scopeMode: 'RANGE', orgs: [], roles: [], positions: [], users: [] }
}

async function loadResources(): Promise<void> {
  resLoading.value = true
  try {
    const [s, m, k] = await Promise.all([getSkills(), getMcps(), getKnowledgeBases()])
    skills.value = s.list
    mcps.value = m.list
    kbs.value = k.list
  } catch {
    ElMessage.error('资源列表加载失败，点击重试')
  } finally {
    resLoading.value = false
  }
}

async function loadDetail(): Promise<void> {
  if (!props.assistantId) return
  loading.value = true
  try {
    const d = await getAssistantDetail(props.assistantId)
    Object.assign(draft, {
      name: d.name,
      avatarType: d.avatarType,
      avatarChar: resolvePresetKey(d.avatarChar, d.assistantId),
      avatarUrl: d.avatarUrl,
      avatarColor: d.avatarColor,
      description: d.description,
      tags: [...d.tags],
      categoryId: d.categoryId,
      prompt: d.prompt ?? '',
      skillIds: (d.skills ?? []).map((s) => s.id),
      mcpIds: (d.mcps ?? []).map((m) => m.id),
      knowledgeBaseIds: (d.knowledgeBases ?? []).map((k) => k.id),
      quickQuestions: [...d.quickQuestions]
    })
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '助理详情加载失败')
    emit('update:modelValue', false)
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    loadResources()
    if (isEdit.value) loadDetail()
    else resetDraft()
    step.value = 1
  }
)

/* ---------------- 头像 ---------------- */

/** 选中系统默认头像：记录 P# 键并同步主色 */
function pickPreset(key: string, color: string): void {
  draft.avatarType = 'char'
  draft.avatarChar = key
  draft.avatarColor = color
  draft.avatarUrl = null
}

/** 移除自定义头像，回退为所选默认头像 */
function removeUpload(): void {
  draft.avatarType = 'char'
  draft.avatarUrl = null
  draft.avatarChar = presetKey.value
  draft.avatarColor = presetColor(presetKey.value)
  ElMessage.success('已移除自定义头像，恢复为默认头像')
}

const uploading = ref(false)

/**
 * 头像上传：先传到后端存储拿到短地址，再写入 avatarUrl。
 * 直接把图片转 base64 会超出 avatarUrl 512 字符限制，因此不再使用 FileReader。
 */
async function handleFileChange(file: { raw?: File }): Promise<void> {
  const raw = file.raw
  if (!raw) return
  if (!raw.type.startsWith('image/')) {
    ElMessage.error('请选择图片文件')
    return
  }
  if (raw.size > 2 * 1024 * 1024) {
    ElMessage.error('图片大小不超过 2MB')
    return
  }
  uploading.value = true
  try {
    const res = await uploadAvatar(raw)
    draft.avatarType = 'image'
    draft.avatarUrl = res.avatarUrl
    ElMessage.success('头像已上传，保存后生效')
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '头像上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

/* ---------------- 标签 / 快速问题 ---------------- */

function addTag(): void {
  const v = tagInput.value.trim()
  if (!v) return
  if (v.length > 8) {
    ElMessage.error('单个标签不超过 8 个字符')
    return
  }
  if (draft.tags.length >= 5) {
    ElMessage.error('最多添加 5 个标签')
    return
  }
  if (draft.tags.includes(v)) {
    ElMessage.error('标签已存在')
    return
  }
  draft.tags.push(v)
  tagInput.value = ''
}

function removeTag(t: string): void {
  draft.tags = draft.tags.filter((x) => x !== t)
}

function addQq(): void {
  const v = qqInput.value.trim()
  if (!v) return
  if (v.length > 30) {
    ElMessage.error('单条问题不超过 30 个字符')
    return
  }
  if (draft.quickQuestions.length >= 6) {
    ElMessage.error('最多添加 6 条快速问题')
    return
  }
  if (draft.quickQuestions.includes(v)) {
    ElMessage.error('该问题已存在')
    return
  }
  draft.quickQuestions.push(v)
  qqInput.value = ''
}

function removeQq(q: string): void {
  draft.quickQuestions = draft.quickQuestions.filter((x) => x !== q)
}

/* ---------------- AI 生成（对齐原型规则） ---------------- */

const categoryName = computed(
  () => props.categories.find((c) => c.categoryId === draft.categoryId)?.name ?? '协同办公'
)

function aiDescDraft(): string {
  const name = draft.name.trim() || '业务助理'
  return `「${name}」面向${categoryName.value}场景，可解答常见问题、讲解制度要点并给出办理指引；回答先给结论、再附依据，涉及个人数据时提醒员工自行核对，无法确认时明确提示转人工处理。`
}

function aiPromptDraft(): string {
  const name = draft.name.trim() || '业务助理'
  const desc = draft.description.trim() || '为员工提供相关业务的问答与操作指引'
  return (
    `你是九牧集团${categoryName.value}条的「${name}」。\n` +
    `职责：${desc}。\n` +
    '回答要求：\n' +
    '1. 先给结论，再给出对应的制度或流程依据；\n' +
    '2. 涉及员工个人数据时，提示员工自行核对；\n' +
    '3. 无法确认的问题必须说明「需人工确认」，不得编造条款编号；\n' +
    '4. 需要走流程的场景，明确指引对应的审批入口。'
  )
}

async function runAi(field: 'description' | 'tags' | 'prompt' | 'quickQuestions'): Promise<void> {
  aiLoading.value[field] = true
  try {
    // 优先走 AI 接口；Mock 下同样返回结构化结果，保持一致
    const res = await aiGenerate({
      field,
      name: draft.name.trim() || '业务助理',
      categoryName: categoryName.value,
      description: draft.description || null,
      tags: [...draft.tags],
      prompt: draft.prompt || null,
      quickQuestions: [...draft.quickQuestions],
      currentValue:
        field === 'description'
          ? draft.description || null
          : field === 'prompt'
            ? draft.prompt || null
            : field === 'tags'
              ? [...draft.tags]
              : [...draft.quickQuestions],
      mode: 'auto'
    })

    if (field === 'description') {
      draft.description = String(res.value).slice(0, 200)
      ElMessage.success('已生成描述草稿，可继续编辑')
    } else if (field === 'prompt') {
      draft.prompt = String(res.value).slice(0, 4000)
      ElMessage.success('已生成提示词草稿，可继续编辑')
    } else if (field === 'tags') {
      const before = draft.tags.length
      const merged = [...draft.tags]
      ;(res.value as string[]).forEach((t) => {
        if (merged.length < 5 && !merged.includes(t)) merged.push(t)
      })
      draft.tags = merged
      const added = merged.length - before
      ElMessage[added ? 'success' : 'error'](added ? `已生成 ${added} 个标签建议，可继续编辑` : '标签已满 5 个')
    } else {
      const before = draft.quickQuestions.length
      const merged = [...draft.quickQuestions]
      ;(res.value as string[]).forEach((q) => {
        if (merged.length < 6 && !merged.includes(q)) merged.push(q)
      })
      draft.quickQuestions = merged
      const added = merged.length - before
      ElMessage[added ? 'success' : 'error'](added ? `已生成 ${added} 条快速问题建议，可继续编辑` : '快速问题已满 6 条')
    }
  } catch {
    // AI 服务不可用时回退到本地模板，保证创建流程不被阻断
    localAi(field)
    if (field === 'tags' || field === 'quickQuestions') {
      ElMessage.warning('AI 服务暂不可用，已使用本地建议')
    }
  } finally {
    aiLoading.value[field] = false
  }
}

/** 本地兜底：AI 服务不可用时按原型同款模板生成 */
function localAi(field: 'description' | 'tags' | 'prompt' | 'quickQuestions'): void {
  if (field === 'description') {
    draft.description = aiDescDraft()
  } else if (field === 'prompt') {
    draft.prompt = aiPromptDraft()
  }
}

/* ---------------- 分类新增 ---------------- */

function onCategoryChange(value: number | undefined): void {
  if (value === undefined) return
  draft.categoryId = value
}

function openCategoryDialog(): void {
  newCategoryName.value = ''
  categoryDialog.value = true
}

async function submitCategory(): Promise<void> {
  const name = newCategoryName.value.trim()
  if (!name) {
    ElMessage.error('请输入分类名称')
    return
  }
  try {
    const item = await createCategory(name)
    emit('create-category', item)
    draft.categoryId = item.categoryId
    categoryDialog.value = false
    ElMessage.success(`分类「${name}」已新增`)
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '新增分类失败')
  }
}

/* ---------------- 步骤切换 / 提交 ---------------- */

const canPrev = computed(() => step.value > 1)
const nextLabel = computed(() => {
  if (step.value < 3) return '下一步'
  return isEdit.value ? '保存' : '完成创建'
})

function goStep(n: number): void {
  step.value = n
}

function prev(): void {
  if (canPrev.value) goStep(step.value - 1)
}

function next(): void {
  if (step.value === 1) {
    if (draft.name.trim().length < 2 || draft.name.trim().length > 20) {
      ElMessage.error('助理名称需为 2-20 个字符')
      return
    }
    const desc = draft.description.trim()
    if (desc.length < 10 || desc.length > 200) {
      ElMessage.error('描述需为 10-200 个字符')
      return
    }
    if (!draft.categoryId) {
      ElMessage.error('请选择所属分类')
      return
    }
    goStep(2)
    return
  }
  if (step.value === 2) {
    if (!draft.prompt.trim()) {
      ElMessage.error('请填写提示词')
      return
    }
    goStep(3)
    return
  }
  void submit()
}

async function submit(): Promise<void> {
  if (shareMode.value === 'yes' && shareScope.value.scopeMode === 'RANGE') {
    const s = shareScope.value
    if (!s.orgs.length && !s.roles.length && !s.positions.length && !s.users.length) {
      ElMessage.error('请选择共享范围')
      return
    }
  }

  saving.value = true
  try {
    const payload: AssistantUpsertPayload = {
      name: draft.name.trim(),
      avatarType: draft.avatarType,
      avatarChar: draft.avatarChar,
      avatarUrl: draft.avatarUrl,
      avatarColor: draft.avatarColor,
      description: draft.description.trim(),
      tags: [...draft.tags],
      categoryId: draft.categoryId,
      prompt: draft.prompt.trim(),
      skillIds: [...draft.skillIds],
      mcpIds: [...draft.mcpIds],
      knowledgeBaseIds: [...draft.knowledgeBaseIds],
      quickQuestions: [...draft.quickQuestions]
    }

    if (isEdit.value && props.assistantId) {
      await updateAssistantApi(props.assistantId, payload)
      ElMessage.success('已保存')
    } else {
      const created = await createAssistantApi(payload)
      if (shareMode.value === 'yes') {
        await submitShareApi({
          assistantIds: [created.assistantId],
          scope: shareScope.value,
          changeNote: undefined
        })
        ElMessage.success('已创建并提交共享审批')
      } else {
        ElMessage.success('创建成功')
      }
    }
    emit('saved')
    emit('update:modelValue', false)
  } catch (e) {
    if (e instanceof ApiError && e.code === 'ASSISTANT_NAME_DUPLICATED') {
      step.value = 1
      ElMessage.error('助理名称已存在，请修改')
    } else {
      ElMessage.error(e instanceof ApiError ? e.message : '保存失败，请稍后重试')
    }
  } finally {
    saving.value = false
  }
}

function close(): void {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :title="isEdit ? `编辑助理 · ${draft.name}` : '手动创建助理'"
    size="760px"
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <div v-loading="loading" class="wizard-body">
      <!-- 步骤条 -->
      <div class="wizard-steps">
        <div class="wz-step" :class="{ active: step === 1, done: step > 1 }">
          <span class="wz-no">{{ step > 1 ? '✓' : 1 }}</span>基础信息
        </div>
        <span class="wz-line" />
        <div class="wz-step" :class="{ active: step === 2, done: step > 2 }">
          <span class="wz-no">{{ step > 2 ? '✓' : 2 }}</span>能力配置
        </div>
        <span class="wz-line" />
        <div class="wz-step" :class="{ active: step === 3 }">
          <span class="wz-no">3</span>{{ isEdit ? '确认提交' : '共享设置' }}
        </div>
      </div>

      <!-- ============ 步骤 1：基础信息 ============ -->
      <div v-show="step === 1" class="wz-pane">
        <div class="form-row">
          <div class="form-item">
            <label class="form-label required">头像</label>
            <div class="avatar-picker">
              <div class="avatar-group-label">系统默认头像</div>
              <div class="avatar-group">
                <div
                  v-for="v in PRESET_AVATARS"
                  :key="v.key"
                  class="avatar-opt avatar-person"
                  :class="{ active: draft.avatarType === 'char' && presetKey === v.key }"
                  :title="`默认头像 ${v.key.slice(1)}`"
                  @click="pickPreset(v.key, v.color)"
                >
                  <img :src="v.src" alt="" />
                </div>
              </div>
              <div class="avatar-group-label">自定义头像</div>
              <div class="avatar-group">
                <template v-if="draft.avatarType === 'image' && draft.avatarUrl">
                  <div class="avatar-opt avatar-preview active" title="当前自定义头像">
                    <img :src="draft.avatarUrl" alt="" />
                  </div>
                  <div class="avatar-ops">
                    <el-upload
                      :auto-upload="false"
                      :show-file-list="false"
                      accept="image/*"
                      :on-change="handleFileChange"
                    >
                      <el-button link type="primary" size="small">替换</el-button>
                    </el-upload>
                    <el-button link type="danger" size="small" @click="removeUpload">移除</el-button>
                  </div>
                </template>
                <el-upload
                  v-else
                  :auto-upload="false"
                  :show-file-list="false"
                  :disabled="uploading"
                  accept="image/*"
                  :on-change="handleFileChange"
                  class="avatar-upload-wrap"
                >
                  <div class="avatar-opt avatar-upload" :class="{ uploading }">
                    <span class="upload-plus">＋</span>
                    <span class="avatar-upload-text">{{ uploading ? '上传中' : '上传' }}</span>
                  </div>
                </el-upload>
              </div>
            </div>
            <div class="form-hint">
              默认展示系统内置头像；可上传自定义头像（JPG/PNG，不超过 2MB），上传后即时预览，支持替换或移除，移除后恢复为所选默认头像
            </div>
          </div>
        </div>

        <div class="form-row two-col">
          <div class="form-item">
            <label class="form-label required">助理名称</label>
            <el-input v-model="draft.name" maxlength="20" placeholder="2-20 个字符，同一公司内唯一" />
            <div class="input-counter">{{ nameLen }}/20</div>
          </div>
          <div class="form-item">
            <label class="form-label required">所属分类</label>
            <el-select :model-value="draft.categoryId" placeholder="请选择分类" class="full" @change="onCategoryChange">
              <el-option v-for="c in categories" :key="c.categoryId" :label="c.name" :value="c.categoryId" />
            </el-select>
            <div v-if="!isEdit" class="form-hint">可点击下方「＋ 新增分类」手动添加</div>
            <el-button link type="primary" size="small" class="add-cat" @click="openCategoryDialog">
              ＋ 新增分类
            </el-button>
          </div>
        </div>

        <div class="form-row">
          <div class="form-item">
            <div class="prompt-tools">
              <label class="form-label required">描述</label>
              <el-button link type="primary" size="small" :loading="aiLoading.description" @click="runAi('description')">
                ✨AI 生成
              </el-button>
            </div>
            <el-input
              v-model="draft.description"
              type="textarea"
              :rows="3"
              maxlength="200"
              placeholder="10-200 个字符，说明该助理能解决什么问题"
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-item">
            <div class="prompt-tools">
              <label class="form-label">自定义标签</label>
              <el-button link type="primary" size="small" :loading="aiLoading.tags" @click="runAi('tags')">
                ✨AI 生成
              </el-button>
            </div>
            <div class="tag-input-wrap">
              <span v-for="t in draft.tags" :key="t" class="tag-chip">
                {{ t }}<span class="x" @click="removeTag(t)">×</span>
              </span>
              <input
                v-if="draft.tags.length < 5"
                v-model="tagInput"
                class="tag-input"
                placeholder="输入后回车生成标签"
                @keydown.enter.prevent="addTag"
              />
            </div>
            <div class="form-hint">最多 5 个，单个标签不超过 8 个字符</div>
          </div>
        </div>
      </div>

      <!-- ============ 步骤 2：能力配置 ============ -->
      <div v-show="step === 2" class="wz-pane">
        <div class="prompt-tools">
          <label class="form-label required">提示词</label>
          <span class="tools-right">
            <el-button link type="primary" size="small" :loading="aiLoading.prompt" @click="runAi('prompt')">
              ✨AI 生成
            </el-button>
            <span class="prompt-counter">{{ promptLen }}/4000</span>
          </span>
        </div>
        <el-input
          v-model="draft.prompt"
          type="textarea"
          :rows="6"
          maxlength="4000"
          placeholder="描述助理的角色设定、回答规则与能力边界"
        />

        <div class="divider" />

        <div class="flex-between">
          <div class="seg-group">
            <div class="seg" :class="{ active: resTab === 'skill' }" @click="switchResTab('skill')">
              技能<span class="seg-count">{{ draft.skillIds.length }}</span>
            </div>
            <div class="seg" :class="{ active: resTab === 'mcp' }" @click="switchResTab('mcp')">
              连接器<span class="seg-count">{{ draft.mcpIds.length }}</span>
            </div>
            <div class="seg" :class="{ active: resTab === 'kb' }" @click="switchResTab('kb')">
              知识库<span class="seg-count">{{ draft.knowledgeBaseIds.length }}</span>
            </div>
          </div>
          <span class="form-hint">均为选填，每项最多 20 个</span>
        </div>

        <div class="res-toolbar">
          <div v-if="resTab !== 'kb'" class="seg-group">
            <div class="seg" :class="{ active: resMarket === 'internal' }" @click="resMarket = 'internal'">内部市场</div>
            <div class="seg" :class="{ active: resMarket === 'external' }" @click="resMarket = 'external'">外部市场</div>
          </div>
          <el-input v-model="resKw" size="small" :placeholder="searchPlaceholder" clearable class="res-search" />
        </div>

        <div v-loading="resLoading" class="res-list">
          <label
            v-for="item in currentCatalog"
            :key="item.id"
            class="res-item"
            :class="{ checked: selectedOf(resTab).includes(item.id) }"
            @click.prevent="toggleRes(item.id)"
          >
            <el-checkbox :model-value="selectedOf(resTab).includes(item.id)" class="res-cb" />
            <span class="res-main">
              <span class="res-name">{{ item.name }}</span>
              <span class="res-desc" :class="{ 'is-hit': item.sub.startsWith('匹配文件') }">{{ item.sub }}</span>
            </span>
          </label>
          <div v-if="!resLoading && !currentCatalog.length" class="res-empty">
            没有匹配的{{ resTab === 'kb' ? '知识库或文件' : resTab === 'skill' ? '技能' : '连接器' }}
          </div>
        </div>

        <div class="divider" />

        <div class="flex-between">
          <label class="form-label">召唤快速问题</label>
          <span class="tools-right">
            <el-button link type="primary" size="small" :loading="aiLoading.quickQuestions" @click="runAi('quickQuestions')">
              ✨AI 生成
            </el-button>
            <span class="form-hint">选填，最多 6 条</span>
          </span>
        </div>
        <div class="tag-input-wrap">
          <span v-for="q in draft.quickQuestions" :key="q" class="tag-chip">
            {{ q }}<span class="x" @click="removeQq(q)">×</span>
          </span>
          <input
            v-if="draft.quickQuestions.length < 6"
            v-model="qqInput"
            class="tag-input"
            placeholder="输入问题后回车添加"
            @keydown.enter.prevent="addQq"
          />
        </div>
      </div>

      <!-- ============ 步骤 3：共享设置 / 确认提交 ============ -->
      <div v-show="step === 3" class="wz-pane">
        <template v-if="needReapprove">
          <el-alert
            type="warning"
            :closable="false"
            show-icon
            :title="`该助理已共享给 ${props.affectedGrantCount} 个授权对象，保存后变更将立即对其生效。`"
          />
          <div class="form-hint mt-base">共享状态与已生效授权范围不变；如需调整授权范围，请在卡片「共享范围」中提交变更申请。</div>
        </template>

        <template v-else-if="isEdit">
          <el-alert type="info" :closable="false" show-icon title="该助理当前未在共享中，保存后仅更新你自己可见的版本。" />
        </template>

        <template v-else>
          <div class="form-item">
            <label class="form-label">是否立即申请共享</label>
            <div class="radio-row">
              <el-radio v-model="shareMode" value="no">暂不共享</el-radio>
              <el-radio v-model="shareMode" value="yes">提交共享申请</el-radio>
            </div>
            <div class="form-hint">选择「提交共享申请」后，需公司管理员审批通过才会出现在他人助理库。</div>
          </div>

          <div v-if="shareMode === 'yes'" class="share-scope-box">
            <div class="divider" />
            <div class="section-title">共享范围</div>
            <ScopePicker
              v-model="shareScope"
              show-limits
              tip="按组织、岗位、角色、人员批量选择，来源维度会把人展开带进「按人员」；最终共享对象是人员。上限：组织 50 个节点、岗位/角色各 50 项、人员 200 人。"
            />
          </div>
          <div class="form-hint mt-base">创建后将生成版本 v1.0</div>
        </template>
      </div>
    </div>

    <template #footer>
      <div class="drawer-footer">
        <el-button @click="close">取消</el-button>
        <el-button v-if="canPrev" @click="prev">上一步</el-button>
        <el-button type="primary" :loading="saving" @click="next">{{ nextLabel }}</el-button>
      </div>
    </template>
  </el-drawer>

  <el-dialog v-model="categoryDialog" title="新增分类" width="420px" append-to-body>
    <div class="form-item">
      <label class="form-label">分类名称</label>
      <el-input v-model="newCategoryName" maxlength="10" placeholder="不超过 10 个字符，如：协同办公" />
      <div class="form-hint">新增后全公司可见，可用于助理归类与列表筛选</div>
    </div>
    <template #footer>
      <el-button @click="categoryDialog = false">取消</el-button>
      <el-button type="primary" @click="submitCategory">确认新增</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.wizard-body {
  min-height: 320px;
}

/* ---------- 步骤条 ---------- */
.wizard-steps {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 520px;
  margin-bottom: 20px;
}

.wz-step {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--at-text-sub);
  white-space: nowrap;
}

.wz-no {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: var(--at-text-sub);
  background: #f4f7f9;
  border-radius: 50%;
}

.wz-step.active {
  color: var(--at-brand);
  font-weight: 600;
}

.wz-step.active .wz-no {
  background: var(--at-brand);
  color: #fff;
}

.wz-step.done .wz-no {
  background: #e8f8f2;
  color: #00875a;
}

.wz-line {
  flex: 1;
  height: 1px;
  background: #ebedf0;
}

/* ---------- 通用表单 ---------- */
.wz-pane {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-row.two-col > .form-item {
  flex: 1;
  min-width: 0;
}

.form-item {
  display: flex;
  flex-direction: column;
  width: 100%;
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
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--at-text-weak);
}

.input-counter {
  text-align: right;
  font-size: 12px;
  color: var(--at-text-weak);
  margin-top: 2px;
}

.prompt-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.prompt-tools .form-label {
  margin-bottom: 0;
}

.tools-right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.prompt-counter {
  font-size: 12px;
  color: var(--at-text-weak);
}

.full {
  width: 100%;
}

.add-cat {
  align-self: flex-start;
  margin-top: 4px;
}

/* ---------- 头像选择 ---------- */
.avatar-picker {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.avatar-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.avatar-group-label {
  width: 100%;
  font-size: 12px;
  color: var(--at-text-sub);
}

.avatar-opt {
  width: 40px;
  height: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  font-size: 13px;
  color: #fff;
  border-radius: 4px;
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.15s, transform 0.15s;
}

.avatar-opt:hover {
  opacity: 0.85;
  transform: translateY(-1px);
}

.avatar-opt.active {
  opacity: 1;
  box-shadow: 0 0 0 2px var(--at-brand);
}

.avatar-opt.avatar-person {
  border-radius: 50%;
  overflow: hidden;
  background: var(--at-bg);
}

.avatar-opt.avatar-person img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.avatar-preview {
  border-radius: 50%;
  overflow: hidden;
  background: var(--at-bg);
}

.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-ops {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.avatar-upload-wrap :deep(.el-upload) {
  display: block;
}

.avatar-upload {
  border: 1px dashed var(--at-border);
  background: #f4f7f9;
  color: var(--at-text-weak);
  overflow: hidden;
  opacity: 1;
}

.avatar-upload:hover {
  border-color: var(--at-brand);
  color: var(--at-brand);
}

.avatar-upload img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-upload-text {
  font-size: 11px;
  line-height: 1;
}

.upload-plus {
  font-size: 16px;
  line-height: 1;
}

/* ---------- 标签输入 ---------- */
.tag-input-wrap {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 4px 8px;
  border: 1px solid var(--at-border);
  border-radius: 4px;
  background: #fff;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  font-size: 12px;
  color: #2563c9;
  background: #eef4ff;
  border: 1px solid #d6e4ff;
  border-radius: 3px;
}

.tag-chip .x {
  cursor: pointer;
  color: var(--at-text-sub);
  line-height: 1;
}

.tag-input {
  flex: 1;
  min-width: 120px;
  border: none;
  outline: none;
  font-size: 13px;
  font-family: inherit;
  color: var(--at-text);
  background: transparent;
}

.tag-input::placeholder {
  color: var(--at-text-weak);
}

/* ---------- 分段控件 ---------- */
.seg-group {
  display: inline-flex;
  padding: 2px;
  background: #f2f3f5;
  border-radius: 6px;
}

.seg {
  display: inline-flex;
  align-items: center;
  padding: 5px 12px;
  border-radius: 4px;
  font-size: 13px;
  color: var(--at-text-sub);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.seg.active {
  background: var(--at-brand);
  color: #fff;
  font-weight: 500;
}

.seg-count {
  display: inline-block;
  min-width: 14px;
  margin-left: 4px;
  padding: 0 4px;
  font-size: 10px;
  line-height: 14px;
  text-align: center;
  border-radius: 7px;
  background: rgba(0, 0, 0, 0.08);
}

.seg.active .seg-count {
  background: rgba(255, 255, 255, 0.28);
}

/* ---------- 资源列表 ---------- */
.res-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.res-search {
  width: 200px;
}

.res-list {
  max-height: 260px;
  min-height: 120px;
  overflow-y: auto;
  border: 1px solid var(--at-border);
  border-radius: 4px;
}

.res-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  cursor: pointer;
  transition: background 0.15s;
}

.res-item:hover {
  background: #f5f7fa;
}

.res-item.checked {
  background: #eef4ff;
}

.res-cb {
  pointer-events: none;
  height: auto;
  margin-top: 1px;
}

.res-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.res-name {
  font-size: 13px;
  color: var(--at-text);
  line-height: 20px;
}

.res-desc {
  font-size: 12px;
  color: var(--at-text-weak);
  line-height: 18px;
}

.res-desc.is-hit {
  color: var(--at-brand);
}

.res-empty {
  padding: 32px 0;
  text-align: center;
  font-size: 12px;
  color: var(--at-text-weak);
}

/* ---------- 其他 ---------- */
.divider {
  height: 1px;
  background: #ebedf0;
}

.flex-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}

.radio-row {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-top: 8px;
}

.mt-base {
  margin-top: 12px;
}

.share-scope-box {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
