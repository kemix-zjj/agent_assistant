/** 统一响应结构（对应 docs/03-接口设计 §2.1） */
export interface ApiResponse<T> {
  code: string
  message: string
  data: T
  traceId: string
}

/** 分页响应（对应 docs/03-接口设计 §2.2） */
export interface PageResult<T> {
  list: T[]
  total: number
  page: number
  pageSize: number
}

/** 分页请求 */
export interface PageQuery {
  page?: number
  pageSize?: number
}

/** 业务错误码（对应 docs/03-接口设计 §2.4） */
export type ApiErrorCode =
  | 'OK'
  | 'PARAM_INVALID'
  | 'UNAUTHENTICATED'
  | 'NO_PERMISSION'
  | 'ASSISTANT_NOT_FOUND'
  | 'APPROVAL_NOT_FOUND'
  | 'ASSISTANT_NAME_DUPLICATED'
  | 'ASSISTANT_NOT_OWNER'
  | 'ASSISTANT_NOT_AVAILABLE'
  | 'ASSISTANT_STATUS_CHANGED'
  | 'APPROVAL_ALREADY_HANDLED'
  | 'SHARE_SCOPE_EMPTY'
  | 'SHARE_SCOPE_EXCEED_LIMIT'
  | 'SHARE_SCOPE_IMMUTABLE'
  | 'RESOURCE_UNAVAILABLE'
  | 'KB_NO_PERMISSION'
  | 'ASSISTANT_ALREADY_SHARED'
  | 'GRANT_INVALID'
  | 'REJECT_REASON_REQUIRED'
  | 'REJECT_REASON_TOO_LONG'
  | 'AI_GENERATE_FAILED'
  | 'CATEGORY_DUPLICATED'
  | 'CATEGORY_NAME_TOO_LONG'
  | 'AVATAR_TOO_LARGE'
  | 'AVATAR_TYPE_INVALID'
  | 'INTERNAL_ERROR'

/** 业务异常：携带 code 与 data，便于页面做字段级定位 */
export class ApiError extends Error {
  code: ApiErrorCode
  data: Record<string, unknown> | null
  traceId: string

  constructor(code: ApiErrorCode, message: string, data: Record<string, unknown> | null, traceId: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.data = data
    this.traceId = traceId
  }
}
