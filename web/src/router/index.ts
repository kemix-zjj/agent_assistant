import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/layouts/BasicLayout.vue'),
    redirect: '/assistants',
    children: [
      {
        path: 'assistants',
        name: 'AssistantList',
        component: () => import('@/views/assistant/AssistantList.vue'),
        meta: { title: '助理团', module: 'assistant' }
      },
      {
        path: 'new-task',
        name: 'NewTask',
        component: () => import('@/views/task/NewTask.vue'),
        meta: { title: '新建任务', module: 'assistant' }
      },
      {
        path: 'approvals',
        name: 'ApprovalCenter',
        component: () => import('@/views/approval/ApprovalCenter.vue'),
        meta: { title: '审批中心', module: 'assistant', requiresAdmin: true }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    redirect: '/assistants'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach((to) => {
  const title = (to.meta.title as string) || ''
  document.title = title ? `${title} · ${import.meta.env.VITE_APP_TITLE}` : import.meta.env.VITE_APP_TITLE
  return true
})

export default router
