<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import ScopePicker from './ScopePicker.vue'
import {
  aiGenerate,
  createCategory,
  createAssistantApi,
  getAssistantDetail,
  getSkills,
  submitShareApi,
  updateAssistantApi,
  uploadAvatar
} from '@/api'
import type {
  CategoryItem,
  AssistantUpsertPayload,
  LocalSkillPayload,
  SkillItem
} from '@/types/assistant'
import type { ScopePayload } from '@/types/scope'
import { emptyScopePayload } from '@/types/scope'
import { ApiError } from '@/types/api'
import { displayVersion } from '@/api/mock'
import { PRESET_AVATARS, resolvePresetKey, presetColor } from '@/utils/avatar'
import { useUserStore } from '@/stores/user'

/**
 * 手动创建 / 编辑助理：三步向导（对齐原型 openWizard）
 * 步骤 1 基础信息 → 步骤 2 能力配置 → 步骤 3 共享设置（编辑时为「确认提交」）
 */
const props = defineProps<{
  modelValue: boolean
  categories: CategoryItem[]
  assistantId?: number | null
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
  quickQuestions: [] as string[],
  /** 已共享过的助理编辑保存时必填，随变更审批单落库 */
  changeNote: ''
})

/** 当前选中的系统默认头像键（P1~P6），编辑历史字符头像时按 ID 稳定回推 */
const presetKey = computed(() => resolvePresetKey(draft.avatarChar, props.assistantId ?? draft.name))

const tagInput = ref('')
const qqInput = ref('')

/** 能力配置：技能来源（内部市场 / 外部市场 / 本地创建） */
const skillSource = ref<'internal' | 'external' | 'local'>('internal')
const resKw = ref('')

/** 本地创建：方式与手动配置表单 */
const localMode = ref<'zip' | 'manual'>('zip')
const localSkill = reactive({ name: '', desc: '', note: '' })
const zipFileName = ref('')
const zipInputRef = ref<HTMLInputElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const dirInputRef = ref<HTMLInputElement | null>(null)
const gutterRef = ref<HTMLElement | null>(null)
const editorRef = ref<HTMLTextAreaElement | null>(null)
const editorText = ref('')
const activeFilePath = ref('')
const collapsedFolders = ref<string[]>([])

/** 步骤 3：是否立即申请共享（仅新建） */
const shareMode = ref<'no' | 'yes'>('no')
const shareScope = ref<ScopePayload>(emptyScopePayload())


const skills = ref<SkillItem[]>([])
const resLoading = ref(false)

/** 本地创建：上传的文件清单（保留相对路径用于文件树） */
interface LocalFile {
  path: string
  name: string
  size: number
  ext: string
  content: string
  original: string
}
const localFiles = ref<LocalFile[]>([])

/** 单文件 5MB、合计 20MB */
const MAX_FILE_SIZE = 5 * 1024 * 1024
const MAX_TOTAL_SIZE = 20 * 1024 * 1024
/** 递归上传时忽略的目录 */
const IGNORED_SEGMENTS = ['__pycache__', '.git', 'node_modules', '.idea', '.vscode']

const aiLoading = ref<Record<string, boolean>>({})
const categoryDialog = ref(false)
const newCategoryName = ref('')

/** 普通员工没有新增分类权限，仅管理员可见「＋ 新增分类」 */
const userStore = useUserStore()

const nameLen = computed(() => draft.name.length)
const promptLen = computed(() => draft.prompt.length)

/** 编辑时的当前共享状态与版本号（用于步骤 3 提示文案） */
const editStatus = ref<string | null>(null)
const editVersion = ref('')
const editHasShared = ref(false)

/** 已共享过且未下架的助理（含调整 / 授权 / 下架被拒）编辑保存后进入变更审批 */
const needReapprove = computed(
  () => isEdit.value && editHasShared.value && editStatus.value !== 'offline'
)

/* ---------------- 技能列表（市场 + 搜索） ---------------- */

const catalogSkills = computed<Array<{ id: string; name: string; sub: string }>>(() => {
  const kw = resKw.value.trim().toLowerCase()
  return skills.value
    .filter((s) => (s.market ?? 'internal') === skillSource.value)
    .filter((s) => !kw || `${s.name} ${s.desc ?? ''}`.toLowerCase().includes(kw))
    .map((s) => ({ id: s.id, name: s.name, sub: s.desc ?? '' }))
})

function toggleSkill(id: string): void {
  const i = draft.skillIds.indexOf(id)
  if (i >= 0) {
    draft.skillIds.splice(i, 1)
    return
  }
  if (draft.skillIds.length >= 20) {
    ElMessage.warning('每项最多 20 个')
    return
  }
  draft.skillIds.push(id)
}

function switchSkillSource(src: 'internal' | 'external' | 'local'): void {
  skillSource.value = src
  resKw.value = ''
}

/* ---------------- 本地创建：文件上传与预览 ---------------- */

function extOf(name: string): string {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i + 1).toLowerCase() : ''
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const localTotalSize = computed(() => localFiles.value.reduce((sum, f) => sum + f.size, 0))

function isIgnoredPath(path: string): boolean {
  return path.split('/').some((seg) => IGNORED_SEGMENTS.includes(seg))
}

/** 追加式上传：同路径覆盖；超出体积限制的文件整体跳过并提示 */
async function addFiles(files: Array<{ path: string; raw: File }>): Promise<void> {
  const accepted: LocalFile[] = []
  let skippedSize = 0
  let skippedIgnored = 0
  for (const { path, raw } of files) {
    if (isIgnoredPath(path)) {
      skippedIgnored += 1
      continue
    }
    if (raw.size > MAX_FILE_SIZE) {
      skippedSize += 1
      continue
    }
    const content = await raw.text()
    accepted.push({
      path,
      name: path.split('/').pop() ?? path,
      size: raw.size,
      ext: extOf(path),
      content,
      original: content
    })
  }

  const merged = new Map(localFiles.value.map((f) => [f.path, f]))
  for (const f of accepted) merged.set(f.path, f)
  const total = [...merged.values()].reduce((sum, f) => sum + f.size, 0)
  if (total > MAX_TOTAL_SIZE) {
    ElMessage.error('文件合计不能超过 20MB')
    return
  }
  localFiles.value = [...merged.values()]
  if (skippedSize) ElMessage.warning(`${skippedSize} 个文件超过单文件 5MB，已跳过`)
  if (skippedIgnored) ElMessage.warning(`${skippedIgnored} 个文件位于忽略目录，已跳过`)
  if (accepted.length) {
    const first = accepted[0].path
    if (!activeFilePath.value) selectLocalFile(first)
  }
}

/** 上传文件夹：webkitRelativePath 保留层级，去掉顶层目录名 */
async function onPickFolder(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement
  const list = Array.from(input.files ?? [])
  await addFiles(
    list.map((raw) => {
      const rel = raw.webkitRelativePath || raw.name
      const segs = rel.split('/')
      return { path: segs.length > 1 ? segs.slice(1).join('/') : rel, raw }
    })
  )
  input.value = ''
}

async function onPickFiles(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement
  const list = Array.from(input.files ?? [])
  await addFiles(list.map((raw) => ({ path: raw.name, raw })))
  input.value = ''
}

function triggerPickFiles(): void {
  fileInputRef.value?.click()
}

function triggerPickFolder(): void {
  dirInputRef.value?.click()
}

function onPickZip(e: Event): void {
  const input = e.target as HTMLInputElement
  const raw = input.files?.[0]
  if (raw) zipFileName.value = raw.name
  input.value = ''
}

function triggerPickZip(): void {
  zipInputRef.value?.click()
}

function removeLocalFile(path: string): void {
  localFiles.value = localFiles.value.filter((f) => f.path !== path)
  if (activeFilePath.value === path) {
    const next = localFiles.value[0]
    if (next) selectLocalFile(next.path)
    else {
      activeFilePath.value = ''
      editorText.value = ''
    }
  }
}

/* ---------- 文件树 ---------- */

interface TreeDirNode {
  key: string
  name: string
  dir: true
  children: TreeNode[]
}
interface TreeFileNode {
  key: string
  name: string
  dir: false
  file: LocalFile
}
type TreeNode = TreeDirNode | TreeFileNode

const localTree = computed<TreeNode[]>(() => {
  const root: TreeDirNode = { key: '', name: '', dir: true, children: [] }
  for (const file of localFiles.value) {
    const segs = file.path.split('/')
    let cursor = root
    for (let i = 0; i < segs.length - 1; i += 1) {
      const key = segs.slice(0, i + 1).join('/')
      let next = cursor.children.find((n): n is TreeDirNode => n.dir && n.key === key)
      if (!next) {
        next = { key, name: segs[i], dir: true, children: [] }
        cursor.children.push(next)
      }
      cursor = next
    }
    cursor.children.push({ key: file.path, name: file.name, dir: false, file })
  }
  const sortNodes = (nodes: TreeNode[]): TreeNode[] => {
    nodes.sort((a, b) => {
      if (a.dir !== b.dir) return a.dir ? -1 : 1
      return a.name.localeCompare(b.name)
    })
    nodes.forEach((n) => {
      if (n.dir) sortNodes(n.children)
    })
    return nodes
  }
  return sortNodes(root.children)
})

/** 折叠态展开成扁平行，支持任意层级 */
const localTreeRows = computed<Array<{ node: TreeNode; depth: number }>>(() => {
  const rows: Array<{ node: TreeNode; depth: number }> = []
  const walk = (nodes: TreeNode[], depth: number): void => {
    for (const node of nodes) {
      rows.push({ node, depth })
      if (node.dir && !collapsedFolders.value.includes(node.key)) {
        walk(node.children, depth + 1)
      }
    }
  }
  walk(localTree.value, 0)
  return rows
})

function toggleFolder(key: string): void {
  const i = collapsedFolders.value.indexOf(key)
  if (i >= 0) collapsedFolders.value.splice(i, 1)
  else collapsedFolders.value.push(key)
}

/* ---------- 文件编辑 ---------- */

const activeFile = computed(() => localFiles.value.find((f) => f.path === activeFilePath.value) ?? null)
const isDirty = computed(() => !!activeFile.value && activeFile.value.content !== activeFile.value.original)

/** 行号随内容行数变化，与编辑区滚动同步 */
const editorLineCount = computed(() => editorText.value.split('\n').length)

function selectLocalFile(path: string): void {
  activeFilePath.value = path
  const file = localFiles.value.find((f) => f.path === path)
  editorText.value = file?.content ?? ''
}

function onEditorInput(): void {
  const file = activeFile.value
  if (!file) return
  file.content = editorText.value
}

function onEditorScroll(): void {
  if (gutterRef.value && editorRef.value) {
    gutterRef.value.scrollTop = editorRef.value.scrollTop
  }
}

function resetActiveFile(): void {
  const file = activeFile.value
  if (!file) return
  file.content = file.original
  editorText.value = file.original
}

function resetLocalSkill(): void {
  localSkill.name = ''
  localSkill.desc = ''
  localSkill.note = ''
  zipFileName.value = ''
  localFiles.value = []
  activeFilePath.value = ''
  editorText.value = ''
  collapsedFolders.value = []
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
    quickQuestions: [],
    changeNote: ''
  })
  editStatus.value = null
  editVersion.value = ''
  editHasShared.value = false
  step.value = 1
  tagInput.value = ''
  qqInput.value = ''
  skillSource.value = 'internal'
  resKw.value = ''
  localMode.value = 'zip'
  resetLocalSkill()
  shareMode.value = 'no'
  shareScope.value = emptyScopePayload()
}

async function loadResources(): Promise<void> {
  resLoading.value = true
  try {
    const s = await getSkills()
    skills.value = s.list
  } catch {
    ElMessage.error('技能列表加载失败，点击重试')
  } finally {
    resLoading.value = false
  }
}

async function loadDetail(): Promise<void> {
  if (!props.assistantId) return
  loading.value = true
  try {
    const d = await getAssistantDetail(props.assistantId)
    skillSource.value = 'internal'
    localMode.value = 'zip'
    resetLocalSkill()
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
      quickQuestions: [...d.quickQuestions],
      changeNote: ''
    })
    // 后端返回本地技能时回填到「本地创建 · 手动配置」
    const local = d.localSkills?.[0]
    if (local) {
      skillSource.value = 'local'
      localMode.value = 'manual'
      localSkill.name = local.name
      localSkill.desc = local.desc
      localSkill.note = local.note
      localFiles.value = (local.files ?? []).map((f) => ({
        path: f.path,
        name: f.path.split('/').pop() ?? f.path,
        size: f.size,
        ext: f.ext,
        content: f.content,
        original: f.content
      }))
      if (localFiles.value.length) selectLocalFile(localFiles.value[0].path)
    }
    editStatus.value = d.shareStatus
    editVersion.value = d.version
    editHasShared.value = d.hasShared
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

/* ---------------- AI 生成（对齐需求 4.1.1.0） ---------------- */

const categoryName = computed(
  () => props.categories.find((c) => c.categoryId === draft.categoryId)?.name ?? '协同办公'
)

/** 各字段的关联输入与当前值，均由 4.1.1.0 的规则表决定 */
function aiPayload(field: 'description' | 'tags' | 'prompt' | 'quickQuestions') {
  return {
    field,
    name: draft.name.trim() || '业务助理',
    categoryName: categoryName.value,
    description: draft.description.trim() || null,
    tags: [...draft.tags],
    prompt: draft.prompt.trim() || null,
    quickQuestions: [...draft.quickQuestions],
    currentValue:
      field === 'description'
        ? draft.description.trim() || null
        : field === 'prompt'
          ? draft.prompt.trim() || null
          : field === 'tags'
            ? [...draft.tags]
            : [...draft.quickQuestions],
    mode: 'auto' as const
  }
}

async function runAi(field: 'description' | 'tags' | 'prompt' | 'quickQuestions'): Promise<void> {
  if (aiLoading.value[field]) return
  aiLoading.value[field] = true
  try {
    const res = await aiGenerate(aiPayload(field))

    if (field === 'description') {
      draft.description = String(res.value).slice(0, 200)
      ElMessage.success('已生成描述草稿，可继续编辑')
    } else if (field === 'prompt') {
      draft.prompt = String(res.value).slice(0, 4000)
      ElMessage.success('已生成提示词草稿，可继续编辑')
    } else if (field === 'tags') {
      if (res.hitLimit) {
        ElMessage.error('标签已满 5 个')
      } else {
        const before = draft.tags.length
        const merged = [...draft.tags]
        ;(res.value as string[]).forEach((t) => {
          if (merged.length < 5 && !merged.includes(t)) merged.push(t)
        })
        draft.tags = merged
        const added = merged.length - before
        ElMessage[added ? 'success' : 'error'](added ? `已生成 ${added} 个标签建议，可继续编辑` : '标签已满 5 个')
      }
    } else if (res.hitLimit) {
      ElMessage.error('快速问题已满 6 条')
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
    // 失败保留原内容，不覆盖已填值
    ElMessage.error('AI 生成失败，请稍后重试')
  } finally {
    aiLoading.value[field] = false
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
/** 编辑保存会触发审批（已共享变更 / 已拒绝共享重新提交）时，按钮改为「保存并提交审批」 */
const submitForApproval = computed(
  () => isEdit.value && (needReapprove.value || editStatus.value === 'rejected')
)
const nextLabel = computed(() => {
  if (step.value < 3) return '下一步'
  if (isEdit.value) return submitForApproval.value ? '保存并提交审批' : '保存'
  return '完成创建'
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
    if (skillSource.value === 'local') {
      if (localMode.value === 'manual') {
        const name = localSkill.name.trim()
        if (name.length < 2 || name.length > 40) {
          ElMessage.error('技能名称需为 2-40 个字符')
          return
        }
        if (!localSkill.desc.trim()) {
          ElMessage.error('请填写技能描述')
          return
        }
      } else if (!zipFileName.value) {
        ElMessage.error('请选择要上传的技能 zip 文件')
        return
      }
    }
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
  // 已共享过的助理编辑保存即转为变更审批，需填写变更说明
  if (isEdit.value && needReapprove.value && !draft.changeNote.trim()) {
    ElMessage.error('请填写变更说明')
    return
  }

  saving.value = true
  try {
    // 本地创建的技能随助理一起提交（zip 模式待后端提供文件上传接口后再补）
    const localSkills: LocalSkillPayload[] = []
    if (skillSource.value === 'local' && localMode.value === 'manual' && localSkill.name.trim()) {
      localSkills.push({
        name: localSkill.name.trim(),
        desc: localSkill.desc.trim(),
        note: localSkill.note.trim(),
        files: localFiles.value.map((f) => ({
          path: f.path,
          size: f.size,
          ext: f.ext,
          content: f.content
        }))
      })
    }

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
      quickQuestions: [...draft.quickQuestions],
      changeNote: draft.changeNote.trim() || undefined,
      ...(localSkills.length ? { localSkills } : {})
    }

    if (isEdit.value && props.assistantId) {
      const detail = await updateAssistantApi(props.assistantId, payload)
      ElMessage.success(
        detail.shareStatus === 'pending'
          ? detail.hasShared
            ? '已提交变更审批，审批通过后版本号尾号 +1'
            : '已提交共享审批'
          : '已保存'
      )
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
  <!-- 复用的线性图标（对齐 prototype SVG 精灵） -->
  <svg class="at-sprite" aria-hidden="true">
    <symbol id="at-icon-ai-spark" viewBox="0 0 24 24">
      <path d="M11 4l1.7 4.3L17 10l-4.3 1.7L11 16l-1.7-4.3L5 10l4.3-1.7z" />
      <path d="M18 14.5l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9z" />
    </symbol>
    <symbol id="at-icon-refresh" viewBox="0 0 24 24">
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </symbol>
  </svg>

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
                      <button type="button" class="avatar-op-btn">
                        <svg class="avatar-op-icon"><use href="#at-icon-refresh" /></svg>
                        替换
                      </button>
                    </el-upload>
                    <button type="button" class="avatar-op-btn is-danger" @click="removeUpload">移除</button>
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
            <template v-if="userStore.isAdmin">
              <div v-if="!isEdit" class="form-hint">可点击下方「＋ 新增分类」手动添加</div>
              <el-button link type="primary" size="small" class="add-cat" @click="openCategoryDialog">
                ＋ 新增分类
              </el-button>
            </template>
          </div>
        </div>

        <div class="form-row">
          <div class="form-item">
            <div class="prompt-tools">
              <label class="form-label required">描述</label>
              <button
                type="button"
                class="btn-ai"
                :class="{ 'is-loading': aiLoading.description }"
                :disabled="aiLoading.description"
                title="根据名称、分类生成描述草稿"
                @click="runAi('description')"
              >
                <svg class="ai-icon"><use href="#at-icon-ai-spark" /></svg>
                AI 生成
              </button>
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
              <button
                type="button"
                class="btn-ai"
                :class="{ 'is-loading': aiLoading.tags }"
                :disabled="aiLoading.tags"
                title="根据助理名称与描述生成标签建议"
                @click="runAi('tags')"
              >
                <svg class="ai-icon"><use href="#at-icon-ai-spark" /></svg>
                AI 生成
              </button>
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
            <button
              type="button"
              class="btn-ai"
              :class="{ 'is-loading': aiLoading.prompt }"
              :disabled="aiLoading.prompt"
              title="根据名称、分类、描述生成提示词草稿"
              @click="runAi('prompt')"
            >
              <svg class="ai-icon"><use href="#at-icon-ai-spark" /></svg>
              AI 生成
            </button>
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
            <div class="seg active">技能<span class="seg-count">{{ draft.skillIds.length }}</span></div>
            <div class="seg seg-disabled" title="暂未开放">
              连接器<span class="seg-badge">待补充</span>
            </div>
            <div class="seg seg-disabled" title="暂未开放">
              知识库<span class="seg-badge">待补充</span>
            </div>
          </div>
          <span class="form-hint">均为选填，每项最多 20 个</span>
        </div>

        <div class="seg-group sub-tabs">
          <div
            class="seg"
            :class="{ active: skillSource === 'internal' }"
            @click="switchSkillSource('internal')"
          >
            内部市场
          </div>
          <div
            class="seg"
            :class="{ active: skillSource === 'external' }"
            @click="switchSkillSource('external')"
          >
            外部市场
          </div>
          <div
            class="seg"
            :class="{ active: skillSource === 'local' }"
            @click="switchSkillSource('local')"
          >
            本地创建
          </div>
        </div>

        <template v-if="skillSource !== 'local'">
          <div class="res-toolbar">
            <span class="form-hint">从市场中选择已有技能</span>
            <el-input v-model="resKw" size="small" placeholder="搜索技能名称" clearable class="res-search" />
          </div>

          <div v-loading="resLoading" class="res-list">
            <label
              v-for="item in catalogSkills"
              :key="item.id"
              class="res-item"
              :class="{ checked: draft.skillIds.includes(item.id) }"
              @click.prevent="toggleSkill(item.id)"
            >
              <el-checkbox :model-value="draft.skillIds.includes(item.id)" class="res-cb" />
              <span class="res-main">
                <span class="res-name">{{ item.name }}</span>
                <span class="res-desc">{{ item.sub }}</span>
              </span>
            </label>
            <div v-if="!resLoading && !catalogSkills.length" class="res-empty">没有匹配的技能</div>
          </div>
        </template>

        <template v-else>
          <div class="mode-cards">
            <button
              type="button"
              class="mode-card"
              :class="{ active: localMode === 'zip' }"
              @click="localMode = 'zip'"
            >
              <span class="mode-title">本地上传 zip</span>
              <span class="mode-sub">上传技能压缩包，无需逐个填写</span>
              <span class="mode-meta">单个 zip ≤ 20MB</span>
            </button>
            <button
              type="button"
              class="mode-card"
              :class="{ active: localMode === 'manual' }"
              @click="localMode = 'manual'"
            >
              <span class="mode-title">手动配置</span>
              <span class="mode-sub">手动填写名称、描述与技能说明</span>
              <span class="mode-meta">适合少量脚本 / 快速验证</span>
            </button>
          </div>

          <div v-if="localMode === 'zip'" class="zip-drop" @click="triggerPickZip">
            <span class="zip-title">{{ zipFileName || '将 zip 拖到此处，或点击选择文件' }}</span>
            <span class="form-hint">包内需包含 SKILL.md</span>
            <span class="btn-ghost">选择 zip 文件</span>
            <input
              ref="zipInputRef"
              type="file"
              accept=".zip"
              class="hidden-input"
              @change="onPickZip"
            />
          </div>

          <div v-else class="local-form">
            <div class="form-row two-col">
              <div class="form-item">
                <label class="form-label required">技能名称</label>
                <el-input v-model="localSkill.name" maxlength="40" placeholder="2-40 个字符，同一公司内唯一" />
              </div>
              <div class="form-item">
                <label class="form-label required">技能描述</label>
                <el-input v-model="localSkill.desc" maxlength="100" placeholder="一句话说明技能用途" />
              </div>
            </div>

            <div class="form-item">
              <div class="prompt-tools">
                <label class="form-label">技能说明</label>
                <span class="tools-right">
                  <span class="form-hint">已上传文件作为该技能的执行逻辑，可在下方直接修改</span>
                </span>
              </div>
              <el-input
                v-model="localSkill.note"
                type="textarea"
                :rows="3"
                maxlength="2000"
                placeholder="描述该技能的适用场景、调用方式与执行步骤"
              />
            </div>

            <div class="form-item">
              <div class="flex-between">
                <div class="btn-group">
                  <span class="btn-ghost" @click="triggerPickFiles">＋ 上传文件</span>
                  <span class="btn-ghost" @click="triggerPickFolder">＋ 上传文件夹</span>
                  <span v-if="activeFile" class="btn-plain" @click="resetActiveFile">撤销当前文件修改</span>
                </div>
                <span class="form-hint">
                  {{ localFiles.length }} 个文件 · 共 {{ formatSize(localTotalSize) }}（追加式上传）
                </span>
              </div>
              <input
                ref="fileInputRef"
                type="file"
                multiple
                class="hidden-input"
                @change="onPickFiles"
              />
              <input
                ref="dirInputRef"
                type="file"
                webkitdirectory
                multiple
                class="hidden-input"
                @change="onPickFolder"
              />

              <div v-if="localFiles.length" class="file-preview">
                <div class="file-tree">
                  <div
                    v-for="row in localTreeRows"
                    :key="row.node.key"
                    class="tree-node"
                    :class="{ 'is-folder': row.node.dir, active: !row.node.dir && activeFilePath === row.node.key }"
                    :style="{ paddingLeft: `${8 + row.depth * 16}px` }"
                    @click="row.node.dir ? toggleFolder(row.node.key) : selectLocalFile(row.node.key)"
                  >
                    <svg
                      v-if="row.node.dir"
                      class="tree-chev"
                      :class="{ collapsed: collapsedFolders.includes(row.node.key) }"
                      viewBox="0 0 12 12"
                    >
                      <path d="M3 4.5L6 7.5L9 4.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    <span v-else class="tree-dot" :class="{ on: row.node.file.content !== row.node.file.original }" />
                    <span class="tree-name">{{ row.node.name }}</span>
                    <span
                      v-if="!row.node.dir"
                      class="tree-remove"
                      title="移除该文件"
                      @click.stop="removeLocalFile(row.node.key)"
                    >
                      ×
                    </span>
                  </div>
                </div>

                <div class="file-editor-pane">
                  <div class="pane-head">
                    <span class="pane-name">{{ activeFilePath }}</span>
                    <span v-if="activeFile" class="tag">{{ activeFile.ext || 'file' }}</span>
                    <span v-if="activeFile" class="form-hint">{{ formatSize(activeFile.size) }}</span>
                    <span class="dirty-tag" :class="{ on: isDirty }">已修改</span>
                  </div>
                  <div class="edit-area">
                    <div ref="gutterRef" class="gutter">
                      <span v-for="n in editorLineCount" :key="n">{{ n }}</span>
                    </div>
                    <textarea
                      ref="editorRef"
                      v-model="editorText"
                      class="editor"
                      spellcheck="false"
                      @input="onEditorInput"
                      @scroll="onEditorScroll"
                    />
                  </div>
                </div>
              </div>
              <div class="form-hint mt-base">
                支持 .py / .md / .txt / .json 等纯文本文件；单文件 ≤ 5MB、合计 ≤ 20MB；文件夹递归上传并自动忽略 __pycache__、.git
              </div>
            </div>
          </div>
        </template>

        <div class="divider" />

        <div class="flex-between">
          <label class="form-label">召唤快速问题</label>
          <span class="tools-right">
            <button
              type="button"
              class="btn-ai"
              :class="{ 'is-loading': aiLoading.quickQuestions }"
              :disabled="aiLoading.quickQuestions"
              title="根据名称、分类生成快速问题建议"
              @click="runAi('quickQuestions')"
            >
              <svg class="ai-icon"><use href="#at-icon-ai-spark" /></svg>
              AI 生成
            </button>
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
            :title="`该助理已共享过（当前版本 ${displayVersion(editVersion)}）。保存后进入变更审批，审批通过时版本号尾号 +1，审批被拒绝则版本号保持不变。`"
          />
          <div class="form-hint mt-base">审批期间原授权范围继续生效，已授权用户继续使用当前已生效版本。</div>
          <div class="form-item mt-base">
            <label class="form-label required">变更说明</label>
            <el-input v-model="draft.changeNote" maxlength="200" placeholder="请说明本次变更内容，便于管理员审批" />
          </div>
        </template>

        <template v-else-if="isEdit">
          <el-alert
            type="info"
            :closable="false"
            show-icon
            :title="editStatus === 'offline'
              ? '该助理已下架，保存后直接生效，不提交审批、不产生版本号。'
              : editStatus === 'rejected'
                ? '该助理共享申请被拒绝，保存后提交新一轮共享审批，审批通过后版本号 V1.0.0。'
                : '该助理当前未在共享中，保存后仅更新你自己可见的版本，不产生版本号。'"
          />
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
              tip="按组织、角色、人员批量选择，来源维度会把人展开带进「按人员」；最终共享对象是人员。上限：组织 50 个节点、角色 50 项、人员 200 人。"
            />
          </div>
          <div class="form-hint mt-base">创建后不产生版本号，首次共享审批通过时记为 V1.0.0</div>
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

/* 图标精灵容器 */
.at-sprite {
  position: absolute;
  width: 0;
  height: 0;
  overflow: hidden;
}

/* AI 生成按钮：对齐 prototype .btn-ai（浅蓝渐变底 + 品牌色描边） */
.btn-ai {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 10px;
  font-family: inherit;
  font-size: 12px;
  line-height: 1;
  color: var(--at-brand);
  background: linear-gradient(90deg, rgba(54, 133, 242, 0.06), rgba(54, 133, 242, 0.16));
  border: 1px solid rgba(54, 133, 242, 0.35);
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.btn-ai:hover {
  color: var(--at-brand-dark);
  border-color: var(--at-brand);
  background: rgba(54, 133, 242, 0.12);
}

.btn-ai:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.btn-ai.is-loading .ai-icon {
  animation: ai-spin 0.9s linear infinite;
}

.ai-icon {
  width: 14px;
  height: 14px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

@keyframes ai-spin {
  to {
    transform: rotate(360deg);
  }
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
  flex-direction: row;
  align-items: center;
  gap: 4px;
}

.avatar-ops :deep(.el-upload) {
  display: block;
}

/* 头像操作按钮：对齐 prototype .btn-text / .btn-danger-text */
.avatar-op-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 4px 8px;
  font-family: inherit;
  font-size: 13px;
  line-height: 1;
  color: var(--at-brand);
  background: none;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.15s;
}

.avatar-op-btn:hover {
  background: rgba(54, 133, 242, 0.1);
}

.avatar-op-btn.is-danger {
  color: var(--at-danger);
}

.avatar-op-btn.is-danger:hover {
  background: rgba(255, 77, 93, 0.1);
}

.avatar-op-icon {
  width: 14px;
  height: 14px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
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

.seg.seg-disabled {
  color: var(--at-text-weak);
  opacity: 0.55;
  cursor: not-allowed;
}

.seg-badge {
  margin-left: 4px;
  padding: 0 4px;
  border-radius: 7px;
  border: 1px solid var(--at-border);
  background: #fff;
  font-size: 10px;
  line-height: 14px;
  color: var(--at-text-weak);
}

.sub-tabs {
  align-self: flex-start;
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

/* ---------- 本地创建 ---------- */
.mode-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.mode-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  text-align: left;
  font-family: inherit;
  color: var(--at-text);
  background: var(--at-bg-card);
  border: 1px solid var(--at-border);
  border-radius: 4px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.mode-card:hover {
  border-color: var(--at-brand);
}

.mode-card.active {
  border-color: var(--at-brand);
  background: #eef4ff;
}

.mode-title {
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
}

.mode-card.active .mode-title {
  color: var(--at-brand);
}

.mode-sub {
  font-size: 12px;
  line-height: 18px;
  color: var(--at-text-sub);
}

.mode-meta {
  font-size: 12px;
  line-height: 18px;
  color: var(--at-text-weak);
}

.zip-drop {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px;
  background: #fafbfc;
  border: 1px dashed var(--at-border);
  border-radius: 4px;
  cursor: pointer;
  text-align: center;
}

.zip-drop:hover {
  border-color: var(--at-brand);
}

.zip-title {
  font-size: 13px;
  color: var(--at-text);
}

.local-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.btn-group {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.btn-ghost {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  border: 1px dashed var(--at-border);
  border-radius: 4px;
  background: var(--at-bg-card);
  color: var(--at-brand);
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  transition: border-color 0.15s;
}

.btn-ghost:hover {
  border-color: var(--at-brand);
}

.btn-plain {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 8px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--at-text-sub);
  font-family: inherit;
  font-size: 12px;
  cursor: pointer;
}

.btn-plain:hover {
  color: var(--at-brand);
  background: #f5f7fa;
}

.hidden-input {
  display: none;
}

.file-preview {
  display: grid;
  grid-template-columns: 220px 1fr;
  height: 300px;
  margin-top: 8px;
  border: 1px solid var(--at-border);
  border-radius: 4px;
  overflow: hidden;
}

.file-tree {
  padding: 8px 0;
  border-right: 1px solid var(--at-border);
  background: var(--at-bg-card);
  overflow-y: auto;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  padding-right: 8px;
  font-family: var(--at-font-mono, ui-monospace, monospace);
  font-size: 12px;
  color: var(--at-text);
  cursor: pointer;
  white-space: nowrap;
}

.tree-node:hover {
  background: #f5f7fa;
}

.tree-node.active {
  background: #eef4ff;
  color: var(--at-brand);
}

.tree-node.is-folder {
  font-family: inherit;
  color: var(--at-text);
}

.tree-chev {
  width: 10px;
  height: 10px;
  flex: 0 0 auto;
  color: var(--at-text-weak);
  transition: transform 0.15s;
}

.tree-chev.collapsed {
  transform: rotate(-90deg);
}

.tree-dot {
  width: 6px;
  height: 6px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: transparent;
}

.tree-dot.on {
  background: var(--at-warning);
}

.tree-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tree-remove {
  flex: 0 0 auto;
  width: 16px;
  font-size: 14px;
  line-height: 1;
  text-align: center;
  color: var(--at-text-weak);
  opacity: 0;
}

.tree-node:hover .tree-remove {
  opacity: 1;
}

.tree-remove:hover {
  color: var(--at-danger);
}

.file-editor-pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #fafbfc;
}

.pane-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--at-bg-card);
  border-bottom: 1px solid var(--at-border);
}

.pane-name {
  font-family: var(--at-font-mono, ui-monospace, monospace);
  font-size: 12px;
  font-weight: 500;
  color: var(--at-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pane-head .tag {
  padding: 0 4px;
  border: 1px solid var(--at-border);
  border-radius: 7px;
  font-size: 10px;
  line-height: 14px;
  color: var(--at-text-weak);
}

.dirty-tag {
  margin-left: auto;
  padding: 0 6px;
  border-radius: 7px;
  background: #fff6e5;
  color: #c77700;
  font-size: 10px;
  line-height: 16px;
  opacity: 0;
}

.dirty-tag.on {
  opacity: 1;
}

.edit-area {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.gutter {
  flex: 0 0 36px;
  padding: 10px 4px 10px 0;
  overflow: hidden;
  text-align: right;
  color: var(--at-text-weak);
  font-family: var(--at-font-mono, ui-monospace, monospace);
  font-size: 12px;
  line-height: 20px;
  user-select: none;
}

.gutter span {
  display: block;
}

.editor {
  flex: 1;
  min-width: 0;
  padding: 10px 12px 10px 0;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--at-text);
  font-family: var(--at-font-mono, ui-monospace, monospace);
  font-size: 12px;
  line-height: 20px;
  tab-size: 4;
  white-space: pre;
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
