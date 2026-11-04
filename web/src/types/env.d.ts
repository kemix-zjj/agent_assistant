/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 后端接口前缀，默认 /api（走 vite 代理） */
  readonly VITE_API_BASE_URL: string
  /** 应用标题 */
  readonly VITE_APP_TITLE: string
  /** 数据源开关：非 'false' 时走前端 Mock 数据（后端未就绪阶段） */
  readonly VITE_USE_MOCK?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
