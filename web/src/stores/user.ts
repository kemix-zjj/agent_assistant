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

/**
 * 视角切换用的登录身份，与后端 master_data 的人员登录号保持一致：
 * 1001 王晓明 / 9001 王建国（管理员）/ 2001 李静（u1）/ 2002 林晓（u2）。
 * 李静、林晓在主数据中被 216 号助理授权，可用来验证「共享助理」链路。
 */
export type ViewRole = 'user' | 'admin' | 'lijing' | 'linxiao'

export const ROLE_USERS: Record<ViewRole, CurrentUser> = {
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
  },
  lijing: {
    userId: '2001',
    name: '李静',
    title: '普通员工',
    deptName: '人力资源部 · 招聘组',
    avatar: '李',
    isAdmin: false
  },
  linxiao: {
    userId: '2002',
    name: '林晓',
    title: '普通员工',
    deptName: '人力资源部 · 薪酬绩效组',
    avatar: '林',
    isAdmin: false
  }
}

/** 视角切换选项：label 由身份数据统一生成，避免侧栏与请求头脱节 */
export const ROLE_OPTIONS: Array<{ label: string; value: ViewRole }> = [
  { label: '视角：普通员工 · 王晓明', value: 'user' },
  { label: '视角：普通员工 · 李静', value: 'lijing' },
  { label: '视角：普通员工 · 林晓', value: 'linxiao' },
  { label: '视角：公司管理员 · 王建国', value: 'admin' }
]

function readRole(): ViewRole {
  const saved = localStorage.getItem('at_role')
  return saved && saved in ROLE_USERS ? (saved as ViewRole) : 'user'
}

export const useUserStore = defineStore('user', () => {
  const role = ref<ViewRole>(readRole())

  const currentUser = computed(() => ROLE_USERS[role.value])
  const isAdmin = computed(() => currentUser.value.isAdmin)

  function switchRole(next: ViewRole) {
    role.value = next
    localStorage.setItem('at_role', next)
  }

  return { role, currentUser, isAdmin, switchRole }
})
