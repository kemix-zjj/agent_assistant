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

/** 已共享助理调整范围 / 平台预置配置范围 */
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

/* ---------------- 字典与资源 ---------------- */

export function getCategories(): Promise<{ list: CategoryItem[] }> {
  if (USE_MOCK) return delay({ list: mock.CATEGORIES })
  return request<{ list: CategoryItem[] }>({ url: '/categories', method: 'get' })
}

export function createCategory(name: string): Promise<CategoryItem> {
  if (USE_MOCK) return delay(mock.addCategory(name))
  return request<CategoryItem>({ url: '/categories', method: 'post', data: { name } })
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

export function aiGenerate(params: AiGenerateParams): Promise<{ field: AiField; value: string | string[]; hitLimit: boolean }> {
  if (USE_MOCK) {
    // Mock：按字段给出符合校验规则的示例内容
    const name = params.name || '业务助理'
    const samples: Record<AiField, string | string[]> = {
      description: `${name}面向${params.categoryName || '本部门'}日常业务场景，可结合制度条款与业务数据给出可执行的处理建议，并标注依据来源。`,
      tags: ['业务问答', '制度检索', '流程指引', '数据分析', '风险提示'],
      prompt: `你是九牧集团的${name}，负责解答${params.categoryName || '本部门'}相关问题。\n回答要求：先给结论，再给制度依据；涉及个人数据须提示自行核对；无法确认时说明「需人工确认」。`,
      quickQuestions: ['这个流程需要哪些审批？', '制度依据是哪一条？', '有异常时应该怎么处理？']
    }
    return delay({ field: params.field, value: samples[params.field], hitLimit: false }, 600)
  }
  return request({ url: '/ai/generate', method: 'post', data: params })
}
