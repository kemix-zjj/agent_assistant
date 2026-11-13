import { request } from './request'
import * as mock from './mock'
import type { AssistantCard, AssistantDetail, AssistantUpsertPayload, DeleteImpact, SummonResult, CategoryItem, ShareSubmitPayload, ListScope, KnowledgeBaseItem, McpItem, SkillItem } from '@/types/assistant'
import type { PageResult } from '@/types/api'
import type { Scope, ScopePayload, ScopeExpandResult } from '@/types/scope'

/**
 * 数据源开关
 * - 默认走 Mock（后端尚未实现），后端就绪后把 VITE_USE_MOCK 设为 false 即可切到真实接口
 * - 两者响应结构完全一致，视图层无需改动
 */
export const USE_MOCK = (import.meta.env.VITE_USE_MOCK ?? 'true') !== 'false'

/** 模拟网络延迟，保证加载态可见 */
function delay<T>(data: T, ms = 180): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(data), ms))
}

/* ---------------- 助理 ---------------- */

export interface AssistantQuery {
  scope: ListScope | string
  categoryId?: number
  keyword?: string
  statusFilter?: string
  subscribeFilter?: string
  page: number
  pageSize: number
}

export function getAssistants(query: AssistantQuery): Promise<PageResult<AssistantCard>> {
  if (USE_MOCK) return delay(mock.queryAssistants(query))
  return request<PageResult<AssistantCard>>({ url: '/assistants', method: 'get', params: query })
}

export function getAssistantDetail(assistantId: number): Promise<AssistantDetail> {
  if (USE_MOCK) return delay(mock.detailOf(assistantId))
  return request<AssistantDetail>({ url: `/assistants/${assistantId}`, method: 'get' })
}

export function createAssistantApi(payload: AssistantUpsertPayload): Promise<AssistantDetail> {
  if (USE_MOCK) return delay(mock.createAssistant(payload))
  return request<AssistantDetail>({ url: '/assistants', method: 'post', data: payload })
}

export function updateAssistantApi(assistantId: number, payload: AssistantUpsertPayload): Promise<AssistantDetail> {
  if (USE_MOCK) return delay(mock.updateAssistant(assistantId, payload))
  return request<AssistantDetail>({ url: `/assistants/${assistantId}`, method: 'put', data: payload })
}

export function deleteAssistantApi(assistantId: number): Promise<{ assistantId: number; deleted: boolean }> {
  if (USE_MOCK) return delay(mock.deleteAssistant(assistantId))
  return request({ url: `/assistants/${assistantId}`, method: 'delete' })
}

export function getDeleteImpact(assistantId: number): Promise<DeleteImpact> {
  if (USE_MOCK) return delay(mock.deleteImpact(assistantId))
  return request<DeleteImpact>({ url: `/assistants/${assistantId}/delete-impact`, method: 'get' })
}

export function summonAssistantApi(assistantId: number, source = 'card'): Promise<SummonResult> {
  if (USE_MOCK) return delay(mock.summonAssistant(assistantId))
  return request<SummonResult>({ url: `/assistants/${assistantId}/summon`, method: 'post', data: { source } })
}

export function updateSubscriptionApi(
  assistantId: number,
  action: 'remove' | 'resubscribe'
): Promise<{ assistantId: number; subscribeStatus: string; subscribeTime: string }> {
  if (USE_MOCK) return delay(mock.updateSubscription(assistantId, action))
  return request({ url: `/assistants/${assistantId}/subscription`, method: 'put', data: { action } })
}

/** 已共享助理调整范围 / 平台内置配置范围 */
export function updateShareScopeApi(assistantId: number, scope: ScopePayload): Promise<{ scope: Scope }> {
  if (USE_MOCK) return delay({ scope: mock.scopeFromPayload(scope) })
  return request({ url: `/assistants/${assistantId}/share-scope`, method: 'put', data: { scope } })
}

export function getShareScopeApi(assistantId: number): Promise<{ scope: Scope | null }> {
  if (USE_MOCK) return delay({ scope: mock.detailOf(assistantId).shareScope })
  return request({ url: `/assistants/${assistantId}/share-scope`, method: 'get' })
}

export function submitShareApi(payload: ShareSubmitPayload): Promise<{ batchNo: string; approvalIds: number[] }> {
  if (USE_MOCK) return delay(mock.submitShare(payload))
  return request({ url: '/shares', method: 'post', data: payload })
}

/** 申请下架已共享助理（管理员审批通过后生效） */
export function submitOfflineApi(
  assistantId: number,
  reason: string
): Promise<{ assistantId: number; shareStatus: string; approvalId: number }> {
  if (USE_MOCK) return delay(mock.submitOffline(assistantId, reason))
  return request({
    url: `/assistants/${assistantId}/offline`,
    method: 'post',
    data: { reason }
  })
}

/* ---------------- 字典与资源 ---------------- */

export function getCategories(): Promise<{ list: CategoryItem[] }> {
  if (USE_MOCK) return delay({ list: mock.CATEGORIES })
  return request<{ list: CategoryItem[] }>({ url: '/categories', method: 'get' })
}

export function createCategory(name: string): Promise<CategoryItem> {
  if (USE_MOCK) return delay(mock.addCategory(name))
  return request<CategoryItem>({ url: '/categories', method: 'post', data: { name } })
}

export function renameCategory(categoryId: number, name: string): Promise<CategoryItem> {
  if (USE_MOCK) return delay(mock.renameCategory(categoryId, name))
  return request<CategoryItem>({ url: `/categories/${categoryId}`, method: 'put', data: { name } })
}

export function deleteCategory(
  categoryId: number
): Promise<{ categoryId: number; deleted: boolean; affectedAssistantCount: number }> {
  if (USE_MOCK) return delay(mock.deleteCategory(categoryId))
  return request({ url: `/categories/${categoryId}`, method: 'delete' })
}

export function getSkills(keyword?: string): Promise<{ list: SkillItem[] }> {
  if (USE_MOCK) {
    const kw = (keyword ?? '').trim()
    return delay({ list: kw ? mock.SKILLS.filter((s) => s.name.includes(kw)) : mock.SKILLS })
  }
  return request<{ list: SkillItem[] }>({ url: '/resources/skills', method: 'get', params: { keyword } })
}

export function getMcps(keyword?: string): Promise<{ list: McpItem[] }> {
  if (USE_MOCK) {
    const kw = (keyword ?? '').trim()
    return delay({ list: kw ? mock.MCPS.filter((m) => m.name.includes(kw)) : mock.MCPS })
  }
  return request<{ list: McpItem[] }>({ url: '/resources/mcps', method: 'get', params: { keyword } })
}

export function getKnowledgeBases(keyword?: string): Promise<{ list: KnowledgeBaseItem[] }> {
  if (USE_MOCK) {
    const kw = (keyword ?? '').trim()
    return delay({ list: kw ? mock.KNOWLEDGE_BASES.filter((k) => k.name.includes(kw)) : mock.KNOWLEDGE_BASES })
  }
  return request<{ list: KnowledgeBaseItem[] }>({ url: '/resources/knowledge-bases', method: 'get', params: { keyword } })
}

/* ---------------- 范围选择 ---------------- */

export function getOrgTree(keyword?: string): Promise<{ tree: mock.OrgNode[] }> {
  if (USE_MOCK) return delay({ tree: mock.ORG_TREE }, 120)
  return request({ url: '/scopes/org-tree', method: 'get', params: { keyword } })
}

export function getRoles(): Promise<{ list: typeof mock.ROLES }> {
  if (USE_MOCK) return delay({ list: mock.ROLES }, 120)
  return request({ url: '/scopes/roles', method: 'get' })
}

export function getPositions(): Promise<{ list: typeof mock.POSITIONS }> {
  if (USE_MOCK) return delay({ list: mock.POSITIONS }, 120)
  return request({ url: '/scopes/positions', method: 'get' })
}

export function searchUsers(params: { keyword?: string; orgIds?: string }): Promise<{ list: typeof mock.USERS }> {
  if (USE_MOCK) {
    const kw = (params.keyword ?? '').trim()
    let list = mock.USERS
    if (params.orgIds) {
      const ids = params.orgIds.split(',')
      list = list.filter((u) => ids.some((id) => (u as { orgId?: string }).orgId === id))
    }
    if (kw) list = list.filter((u) => u.name.includes(kw) || u.jobNo.includes(kw))
    return delay({ list }, 120)
  }
  return request({ url: '/scopes/users', method: 'get', params })
}

export function expandScope(payload: ScopePayload): Promise<ScopeExpandResult> {
  if (USE_MOCK) {
    const scope = mock.scopeFromPayload(payload)
    return delay({
      scopeMode: scope.scopeMode,
      grantTotal: scope.grantTotal,
      users: mock.currentGrantUsers(scope),
      counts: {
        org: payload.orgs.length,
        role: payload.roles.length,
        position: payload.positions.length,
        user: scope.users.length
      },
      limits: { org: 50, role: 50, position: 50, user: 200 }
    })
  }
  return request<ScopeExpandResult>({ url: '/scopes/expand', method: 'post', data: payload })
}

/* ---------------- 审批 ---------------- */

export function getApprovals(params: { status?: string; approvalType?: string; page: number; pageSize: number }): Promise<PageResult<import('@/types/approval').ApprovalCard>> {
  if (USE_MOCK) return delay(mock.queryApprovals(params))
  return request({ url: '/approvals', method: 'get', params })
}

export function getPendingCount(): Promise<{ pendingCount: number }> {
  if (USE_MOCK) return delay({ pendingCount: mock.pendingCount() }, 80)
  return request({ url: '/approvals/pending-count', method: 'get' })
}

export function getApprovalDetail(approvalId: number): Promise<import('@/types/approval').ApprovalDetail> {
  if (USE_MOCK) {
    const row = mock.findApproval(approvalId)
    const { requestScope, ...detail } = row
    void requestScope
    return delay(detail)
  }
  return request({ url: `/approvals/${approvalId}`, method: 'get' })
}

export function adjustApprovalScope(
  approvalId: number,
  scope: ScopePayload
): Promise<{ scope: Scope; scopeDiff: import('@/types/approval').ScopeDiff | null }> {
  if (USE_MOCK) return delay(mock.adjustApprovalScope(approvalId, mock.scopeFromPayload(scope)))
  return request({ url: `/approvals/${approvalId}/scope`, method: 'put', data: { scope } })
}

export function approveApproval(approvalId: number, comment?: string): Promise<import('@/types/approval').ApprovalDecisionResult> {
  if (USE_MOCK) return delay(mock.approve(approvalId))
  return request({ url: `/approvals/${approvalId}/approve`, method: 'post', data: { comment } })
}

export function rejectApproval(approvalId: number, rejectReason: string): Promise<import('@/types/approval').ApprovalDecisionResult> {
  if (USE_MOCK) return delay(mock.reject(approvalId, rejectReason))
  return request({ url: `/approvals/${approvalId}/reject`, method: 'post', data: { rejectReason } })
}

/* ---------------- AI ---------------- */

export type AiField = 'description' | 'tags' | 'prompt' | 'quickQuestions'

export interface AiGenerateParams {
  field: AiField
  name: string
  categoryName?: string
  description?: string | null
  tags?: string[]
  prompt?: string | null
  quickQuestions?: string[]
  currentValue: string | string[] | null
  mode?: 'auto' | 'generate' | 'polish'
}

/**
 * Mock 实现：规则与后端 ai_service 保持一致（需求 4.1.1.0）
 * - auto 模式按 currentValue 是否为空判定生成 / 润色
 * - 描述：名称 + 分类；润色时保留原描述再补充
 * - 标签：名称 + 分类 + 描述，补足至 5 个
 * - 提示词：名称 + 描述 + 分类 + 标签
 * - 快速问题：名称 + 描述，补足至 6 条
 */
function mockAiGenerate(params: AiGenerateParams): { field: AiField; value: string | string[]; hitLimit: boolean } {
  const name = params.name.trim() || '业务助理'
  const category = params.categoryName || '本部门'
  const description = (params.description ?? '').trim()
  const current = params.currentValue
  const hasContent = typeof current === 'string' ? !!current.trim() : Array.isArray(current) && current.length > 0
  const mode = params.mode && params.mode !== 'auto' ? params.mode : hasContent ? 'polish' : 'generate'

  if (params.field === 'description') {
    if (mode === 'polish' && typeof current === 'string' && current.trim()) {
      const extra = `${category}场景下会同步标注制度依据，涉及个人数据提醒自行核对。`
      const base = current.trim().replace(/[。；;，, ]+$/, '')
      return {
        field: 'description',
        value: current.includes(extra) ? current : `${base}。${extra}`.slice(0, 200),
        hitLimit: false
      }
    }
    return {
      field: 'description',
      value: `「${name}」面向${category}场景，可解答常见问题、讲解制度要点并给出办理指引；回答先给结论、再附依据，涉及个人数据时提醒员工自行核对，无法确认时明确提示转人工处理。`,
      hitLimit: false
    }
  }

  if (params.field === 'tags') {
    const existing = Array.isArray(current) ? current.slice(0, 5) : []
    if (existing.length >= 5) return { field: 'tags', value: existing, hitLimit: true }
    const verbPrefixes = ['解答', '回答', '负责', '支持', '提供', '输出', '用于', '面向', '通过', '包括', '帮助', '协助', '针对', '结合']
    const stripVerb = (t: string): string => {
      const hit = verbPrefixes.find((p) => t.startsWith(p) && t.length > p.length)
      return hit && t.length - hit.length <= 8 ? t.slice(hit.length) : t
    }
    const candidates = [
      ...description
        .split(/[，。、；：（）()·\s/-]+/)
        .map((t) => stripVerb(t.trim()))
        .filter((t) => t.length >= 1 && t.length <= 8),
      '业务问答',
      '制度检索',
      '流程指引',
      '数据分析',
      '风险提示'
    ]
    const merged = [...existing]
    candidates.forEach((t) => {
      if (merged.length < 5 && !merged.includes(t)) merged.push(t)
    })
    return { field: 'tags', value: merged, hitLimit: false }
  }

  if (params.field === 'prompt') {
    if (mode === 'polish' && typeof current === 'string' && current.trim()) {
      const tail = `补充要求：回答时结合「${name}」的服务范围（${description || `${category}日常业务`}），先确认关键前提；涉及跨部门流程时给出责任部门，信息不足时先追问再作答。`
      return {
        field: 'prompt',
        value: current.includes(tail) ? current : `${current.trim()}\n${tail}`.slice(0, 4000),
        hitLimit: false
      }
    }
    const tags = (params.tags ?? []).slice(0, 5)
    const lines = [`你是${category}的「${name}」，负责解答${category}相关问题。`]
    if (description) lines.push(`服务背景：${description}`)
    if (tags.length) lines.push(`擅长方向：${tags.join('、')}`)
    lines.push(
      '回答要求：\n1. 先给结论，再给出对应的制度或流程依据；\n2. 涉及员工个人数据时，提示员工自行核对；\n3. 无法确认的问题必须说明「需人工确认」，不得编造条款编号；\n4. 需要走流程的场景，明确指引对应的审批入口。'
    )
    return { field: 'prompt', value: lines.join('\n'), hitLimit: false }
  }

  const existing = Array.isArray(current) ? current.slice(0, 6) : []
  if (existing.length >= 6) return { field: 'quickQuestions', value: existing, hitLimit: true }
  const candidates = [
    `${name}能帮我做什么？`,
    `如何正确使用「${name}」？`,
    `${name}常见问题有哪些？`,
    `${name}的回答依据是什么？`,
    '对应的制度依据是哪一条？',
    '办理需要准备哪些材料？',
    '出现异常时应该怎么处理？',
    '处理时限是怎么规定的？'
  ]
  const merged = [...existing]
  candidates.forEach((q) => {
    if (merged.length < 6 && !merged.includes(q)) merged.push(q)
  })
  return { field: 'quickQuestions', value: merged, hitLimit: false }
}

export function aiGenerate(params: AiGenerateParams): Promise<{ field: AiField; value: string | string[]; hitLimit: boolean }> {
  if (USE_MOCK) return delay(mockAiGenerate(params), 600)
  // 大模型为推理模型，响应耗时可能达数十秒，单独放宽超时（实例默认 20s）
  return request({ url: '/ai/generate', method: 'post', data: params, timeout: 45000 })
}

/* ---------------- 头像上传 ---------------- */

/**
 * 上传头像：真实环境走后端本地存储，返回可直接写入 avatarUrl 的短路径。
 * Mock 下用 objectURL 预览，退出页面即失效。
 */
export function uploadAvatar(file: File): Promise<{ objectKey: string; avatarUrl: string }> {
  if (USE_MOCK) {
    return delay({ objectKey: `avatar/mock/${file.name}`, avatarUrl: URL.createObjectURL(file) })
  }
  const form = new FormData()
  form.append('file', file)
  // 覆盖实例默认的 application/json，axios 会自动补 multipart 边界
  return request({ url: '/common/avatar-upload', method: 'post', data: form, headers: { 'Content-Type': 'multipart/form-data' } })
}
