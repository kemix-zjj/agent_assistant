import type { Scope, ScopePayload } from './scope'

/** 助理来源（docs/03 §3.1；shared 为查询派生，不落库） */
export type AssistantSource = 'platform' | 'custom' | 'thirdparty' | 'shared'

/** 共享状态（需求 4.0 共享状态与文案统一） */
export type ShareStatus = 'unshared' | 'pending' | 'approved' | 'rejected'

/** 订阅状态（被授权方自主开关） */
export type SubscribeStatus = 'subscribed' | 'removed'

/** 列表范围 */
export type ListScope = 'all' | 'mine' | 'shared'

/** 头像形态 */
export type AvatarType = 'char' | 'image'

/** 卡片可执行操作（后端下发，前端据此渲染按钮） */
export type AssistantAction = 'summon' | 'edit' | 'delete' | 'shareScope' | 'remove' | 'resubscribe'

/** 列表卡片项（GET /assistants，不含 prompt） */
export interface AssistantCard {
  assistantId: number
  name: string
  avatarType: AvatarType
  avatarChar: string | null
  avatarUrl: string | null
  avatarColor: string
  categoryId: number
  categoryName: string
  tags: string[]
  description: string
  descriptionTruncated: string
  source: AssistantSource
  shareStatus: ShareStatus | null
  subscribeStatus: SubscribeStatus | null
  version: string
  ownerName: string | null
  ownerTitle: string | null
  sharedFrom: { ownerName: string; ownerDeptName: string } | null
  rejectReason: string | null
  lastApproverName: string | null
  lastApproveTime: string | null
  authorizedCount: number
  createdAt: string
  updatedAt: string
  actions: AssistantAction[]
}

/** 资源市场：内部市场（集团自研沉淀）/ 外部市场（生态市场上架） */
export type ResourceMarket = 'internal' | 'external'

/** 能力组成资源项 */
export interface SkillItem {
  id: string
  name: string
  desc?: string
  market?: ResourceMarket
}

export interface McpItem {
  id: string
  name: string
  type?: string
  market?: ResourceMarket
}

export interface KnowledgeBaseItem {
  id: string
  name: string
  documentCount?: number
  market?: ResourceMarket
  files?: string[]
}

/** 版本记录（GET /assistants/{id}） */
export interface VersionHistoryItem {
  version: string
  action: string
  actionName: string
  operatorName: string
  remark: string
  createdAt: string
}

/** 助理详情（GET /assistants/{id}） */
export interface AssistantDetail {
  assistantId: number
  name: string
  avatarType: AvatarType
  avatarChar: string | null
  avatarUrl: string | null
  avatarColor: string
  description: string
  tags: string[]
  categoryId: number
  categoryName: string
  source: AssistantSource
  shareStatus: ShareStatus | null
  version: string
  ownerName: string | null
  ownerDeptName: string | null
  createdAt: string
  updatedAt: string
  /** 被授权方视角下为 null（需求 5.2） */
  prompt: string | null
  skills: SkillItem[] | null
  mcps: McpItem[] | null
  knowledgeBases: KnowledgeBaseItem[] | null
  quickQuestions: string[]
  shareScope: Scope | null
  versionHistory: VersionHistoryItem[]
}

/** 创建 / 编辑助理请求体（PUT 为全量覆盖） */
export interface AssistantUpsertPayload {
  name: string
  avatarType: AvatarType
  avatarChar: string | null
  avatarUrl: string | null
  avatarColor: string
  description: string
  tags: string[]
  categoryId: number
  prompt: string
  skillIds: string[]
  mcpIds: string[]
  knowledgeBaseIds: string[]
  quickQuestions: string[]
}

/** 删除影响面（GET /assistants/{id}/delete-impact） */
export interface DeleteImpact {
  assistantId: number
  name: string
  authorizedCount: number
  pendingApplyCount: number
}

/** 召唤响应（POST /assistants/{id}/summon） */
export interface SummonResult {
  sessionId: string
  sessionTitle: string
  assistantId: number
  assistantName: string
  AssistantAvatar: { type: AvatarType; char: string; color: string; url?: string | null }
  quickQuestions: string[]
  createdAt: string
}

/** 分类字典项 */
export interface CategoryItem {
  categoryId: number
  name: string
  isBuiltin: boolean
  sortNo: number
}

/** 共享请求（POST /shares） */
export interface ShareSubmitPayload {
  assistantIds: number[]
  scope: ScopePayload
  changeNote?: string
}

export type { Scope, ScopePayload }
