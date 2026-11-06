import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig } from 'axios'
import { ApiError } from '@/types/api'
import type { ApiResponse, ApiErrorCode } from '@/types/api'

/**
 * 统一请求封装（对应 docs/03-接口设计 §2.1）
 * - 响应拦截器剥离 { code, message, data, traceId } 外壳，直接返回 data
 * - code !== 'OK' 时抛出 ApiError，便于页面做字段级定位
 */
const instance: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' }
})

/**
 * 网关接好前，前端按当前视角模拟登录态；中文姓名需百分号编码后再放进请求头。
 * 账号 ID 与后端 master_data 的人员登录号对应，李静/林晓可验证共享助理链路。
 */
const ROLE_PROFILE: Record<string, { id: string; name: string; dept: string }> = {
  user: { id: '1001', name: '王晓明', dept: '人力资源部 · 招聘组' },
  admin: { id: '9001', name: '王建国', dept: '人力资源部' },
  lijing: { id: '2001', name: '李静', dept: '人力资源部 · 招聘组' },
  linxiao: { id: '2002', name: '林晓', dept: '人力资源部 · 薪酬绩效组' }
}

instance.interceptors.request.use((config) => {
  const role = localStorage.getItem('at_role') || 'user'
  const profile = ROLE_PROFILE[role] ?? ROLE_PROFILE.user
  config.headers.set('X-User-Id', profile.id)
  config.headers.set('X-Company-Id', '1')
  config.headers.set('X-User-Name', encodeURIComponent(profile.name))
  config.headers.set('X-User-Dept', encodeURIComponent(profile.dept))
  return config
})

instance.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse<unknown>
    // 非统一结构（如二进制）直接放行
    if (!body || typeof body !== 'object' || !('code' in body)) {
      return response
    }
    if (body.code !== 'OK') {
      throw new ApiError(
        body.code as ApiErrorCode,
        body.message,
        (body.data as Record<string, unknown>) ?? null,
        body.traceId
      )
    }
    response.data = body.data
    return response
  },
  (error) => {
    const body = error.response?.data as ApiResponse<unknown> | undefined
    if (body?.code) {
      throw new ApiError(
        body.code as ApiErrorCode,
        body.message,
        (body.data as Record<string, unknown>) ?? null,
        body.traceId
      )
    }
    throw new ApiError('INTERNAL_ERROR', '操作失败，请稍后重试', null, '')
  }
)

/** 统一取出 data，供 api 层函数使用 */
export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const response = await instance.request<T>(config)
  return response.data
}

export default instance
