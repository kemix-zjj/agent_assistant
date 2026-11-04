import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getPendingCount } from '@/api'
import { useUserStore } from './user'

/** 待审批数量角标：审批中心按钮与审批页共用，审批决策后主动刷新 */
export const useApprovalStore = defineStore('approval', () => {
  const pendingCount = ref(0)
  const loading = ref(false)

  async function refreshPendingCount() {
    const user = useUserStore()
    if (!user.isAdmin) {
      pendingCount.value = 0
      return
    }
    loading.value = true
    try {
      const data = await getPendingCount()
      pendingCount.value = data.pendingCount
    } catch {
      // 角标加载失败时隐藏，不影响按钮可点（REQ-APR-LIST-001 异常分支）
      pendingCount.value = 0
    } finally {
      loading.value = false
    }
  }

  return { pendingCount, loading, refreshPendingCount }
})
