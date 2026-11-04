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

instance.interceptors.request.use((config) => {
  const role = localStorage.getItem('at_role') || 'user'
  config.headers.set('X-User-Id', role === 'admin' ? '9001' : '1001')
  config.headers.set('X-Company-Id', '1')
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
