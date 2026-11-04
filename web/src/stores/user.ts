import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/** 当前登录用户与视角（原型通过侧栏「视角」切换普通员工 / 公司管理员） */
export interface CurrentUser {
  userId: string
  name: string
  title: string
  deptName: string
  avatar: string
  isAdmin: boolean
}

const ROLE_USERS: Record<'user' | 'admin', CurrentUser> = {
  user: {
    userId: '1001',
    name: '王晓明',
    title: '普通员工',
    deptName: '人力资源部 · 招聘组',
    avatar: '王',
    isAdmin: false
  },
  admin: {
    userId: '9001',
    name: '王建国',
    title: '公司管理员',
    deptName: '人力资源部',
    avatar: '管',
    isAdmin: true
  }
}

export const useUserStore = defineStore('user', () => {
  const role = ref<'user' | 'admin'>(
    (localStorage.getItem('at_role') as 'user' | 'admin') || 'user'
  )

  const currentUser = computed(() => ROLE_USERS[role.value])
  const isAdmin = computed(() => currentUser.value.isAdmin)

  function switchRole(next: 'user' | 'admin') {
    role.value = next
    localStorage.setItem('at_role', next)
  }

  return { role, currentUser, isAdmin, switchRole }
})
