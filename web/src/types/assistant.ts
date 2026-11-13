import type { Scope, ScopePayload } from './scope'

/** 助理来源（docs/03 §3.1；shared 为查询派生，不落库） */
export type AssistantSource = 'platform' | 'custom' | 'thirdparty' | 'shared'

/** 共享状态（需求 4.0 共享状态与文案统一；审批中统一为 pending，由 pendingType 区分四类） */
export type ShareStatus = 'unshared' | 'pending' | 'approved' | 'rejected' | 'offline'

/** 审批子类 / 拒绝子类：共享审批 / 调整审批 / 授权审批 / 下架审批 */
export type ApproveSubType = 'share' | 'change' | 'scope' | 'offline'

/** 订阅状态（被授权方自主开关） */
export type SubscribeStatus = 'subscribed' | 'removed'

/** 列表范围（本期仅三个页签） */
export type ListScope = 'all' | 'mine' | 'shared'

/** 头像形态 */
export type AvatarType = 'char' | 'image'

/** 卡片可执行操作（后端下发，前端据此渲染按钮） */
export type AssistantAction =
  | 'summon'
  | 'edit'
  | 'delete'
  | 'share'
  | 'resubmit'
  | 'shareScope'
  | 'offline'
  | 'remove'
  | 'resubscribe'

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
  /** 审批子类：仅「我的助理」范围返回 */
  pendingType: ApproveSubType | null
  /** 拒绝子类：仅「我的助理」范围返回 */
  rejectType: ApproveSubType | null
  subscribeStatus: SubscribeStatus | null
  /** 空串表示「未发布」 */
  version: string
  /** 是否曾共享成功过，决定删除资格与版本号口径 */
  hasShared: boolean
  ownerName: string | null
  ownerTitle: string | null
  sharedFrom: { ownerName: string; ownerDeptName: string } | null
  rejectReason: string | null
  offlineReason: string | null
  lastApproverName: string | null
  lastApproveTime: string | null
  authorizedCount: number
  createdAt: string
  updatedAt: string
  authorizedAt?: string | null
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
  pendingType: ApproveSubType | null
  rejectType: ApproveSubType | null
  subscribeStatus: SubscribeStatus | null
  version: string
  hasShared: boolean
  ownerName: string | null
  ownerDeptName: string | null
  rejectReason: string | null
  offlineReason: string | null
  lastApproverName: string | null
  lastApproveTime: string | null
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
  /** 后端派生的操作按钮，与列表卡片同源 */
  actions: AssistantAction[]
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
  /** 已共享过的助理编辑保存会转为变更审批，需带变更说明 */
  changeNote?: string
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
