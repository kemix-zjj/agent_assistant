import type { AvatarType } from './assistant'
import type { Scope } from './scope'

/** 审批单类型（本期实现 share / scope_change，offline 预留） */
export type ApprovalType = 'share' | 'scope_change' | 'offline'

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'terminated'

/** 待审批列表项（GET /approvals，列表视图与卡片视图共用） */
export interface ApprovalCard {
  approvalId: number
  approvalNo: string
  approvalType: ApprovalType
  approvalTypeName: string
  assistantId: number
  assistantName: string
  AssistantAvatar: { type: AvatarType; char: string; color: string; url?: string | null }
  assistantVersion: string
  categoryName: string
  tags: string[]
  submitterName: string
  submitterDept: string
  submitTime: string
  scopeSummary: string
  scopeMode: 'RANGE' | 'PUBLIC'
  changeNote: string | null
}

/** 范围差异（管理员调整后与申请的差量） */
export interface ScopeDiff {
  addedCount: number
  removedCount: number
  added: Array<{ dim: string; id: string; name: string }>
  removed: Array<{ dim: string; id: string; name: string }>
}

/** 审批详情（GET /approvals/{id}） */
export interface ApprovalDetail {
  approvalId: number
  approvalNo: string
  approvalType: ApprovalType
  status: ApprovalStatus
  assistant: {
    assistantId: number
    name: string
    avatar: { type: AvatarType; char: string; color: string; url?: string | null }
    description: string
    tags: string[]
    categoryName: string
    prompt: string
    skills: Array<{ id: string; name: string }>
    mcps: Array<{ id: string; name: string }>
    knowledgeBases: Array<{ id: string; name: string }>
    ownerName: string
    ownerDeptName: string
    version: string
  }
  submitterName: string
  submitterDept: string
  submitTime: string
  scopeAdjusted: boolean
  scope: Scope
  scopeDiff: ScopeDiff | null
  assistantConfigChanged?: boolean
}

/** 审批决策响应 */
export interface ApprovalDecisionResult {
  approvalId: number
  status: ApprovalStatus
  assistantId: number
  shareStatus: string
  grantTotal?: number
  rejectReason?: string
  approveTime: string
}
