import type { AvatarType } from './assistant'
import type { Scope } from './scope'

/** 审批单类型：共享申请 / 授权申请 / 调整申请 / 下架申请 */
export type ApprovalType = 'share' | 'scope' | 'change' | 'offline'

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
  /** 下架申请的申请原因；共享 / 范围变更申请为变更说明 */
  changeNote?: string | null
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
  /** 下架申请没有授权范围，可能为 null */
  scope: Scope | null
  /** 范围变更申请：变更前的生效范围；其他类型为 null */
  previousScope?: Scope | null
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
