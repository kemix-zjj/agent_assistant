/** 共享范围对象：四处场景（创建向导 / 共享提交 / 范围弹窗 / 审批调整）共用（docs/03 §2.3） */
export type ScopeMode = 'RANGE' | 'PUBLIC'

export type ScopeDim = 'org' | 'role' | 'position' | 'user'

export interface ScopeOrgItem {
  id: string
  name: string
}

export interface ScopeRoleItem {
  id: string
  name: string
}

export interface ScopePositionItem {
  id: string
  name: string
}

export interface ScopeUserItem {
  id: string
  name: string
  deptName?: string
}

export interface Scope {
  scopeMode: ScopeMode
  orgs: ScopeOrgItem[]
  roles: ScopeRoleItem[]
  positions: ScopePositionItem[]
  users: ScopeUserItem[]
  grantTotal: number
  summary: string
}

/** 范围选择上限（docs/03 §5.4） */
export interface ScopeLimits {
  org: number
  role: number
  position: number
  user: number
}

/** 提交给后端的范围请求体：只传 ID，不含名称与统计 */
export interface ScopePayload {
  scopeMode: ScopeMode
  orgs: string[]
  roles: string[]
  positions: string[]
  users: string[]
}

export interface ScopeExpandResult {
  scopeMode: ScopeMode
  grantTotal: number
  users: Array<ScopeUserItem & { sources: ScopeDim[] }>
  counts: Record<ScopeDim, number>
  limits: ScopeLimits
}

export const EMPTY_SCOPE: Scope = {
  scopeMode: 'RANGE',
  orgs: [],
  roles: [],
  positions: [],
  users: [],
  grantTotal: 0,
  summary: ''
}

export const DEFAULT_SCOPE_LIMITS: ScopeLimits = {
  org: 50,
  role: 50,
  position: 50,
  user: 200
}
