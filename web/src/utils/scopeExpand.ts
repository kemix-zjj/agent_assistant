/** 范围展开的本地计算工具。
 *
 * 真实后端模式下，组织树 / 人员 / 角色 / 岗位由 `GET /scopes/*` 加载，
 * 这里基于已加载的数据在本地即时展开人员，用于选择过程中的实时预览；
 * 最终提交仍由后端 `POST /scopes/expand` 与保存接口重新计算，保证口径一致。
 */

export interface OrgNodeLike {
  id: string
  name: string
  children?: OrgNodeLike[]
}

export interface UserLike {
  id: string
  name: string
  jobNo?: string
  orgId?: string
  positionId?: string
  roles?: string[]
}

/** 组织节点自身 + 全部下级节点 ID */
export function orgIdsUnder(tree: OrgNodeLike[], orgId: string): string[] {
  const out: string[] = []

  const collect = (node: OrgNodeLike): void => {
    out.push(node.id)
    ;(node.children ?? []).forEach(collect)
  }

  const walk = (nodes: OrgNodeLike[]): void => {
    for (const node of nodes) {
      if (node.id === orgId) {
        collect(node)
        return
      }
      if (node.children?.length) walk(node.children)
    }
  }

  walk(tree)
  return out
}

export interface ScopeSelection {
  orgs: string[]
  roles: string[]
  positions: string[]
  users: string[]
}

/** 来源维度展开出的人员（组织含下级 / 角色 / 岗位 ∪ 直接添加） */
export function expandUserIds(
  selection: ScopeSelection,
  tree: OrgNodeLike[],
  users: UserLike[]
): string[] {
  const picked = new Set<string>()

  if (selection.orgs.length) {
    const allowed = new Set<string>()
    selection.orgs.forEach((orgId) => orgIdsUnder(tree, orgId).forEach((id) => allowed.add(id)))
    users.forEach((u) => {
      if (u.orgId && allowed.has(u.orgId)) picked.add(u.id)
    })
  }

  if (selection.roles.length) {
    const roles = new Set(selection.roles)
    users.forEach((u) => {
      if ((u.roles ?? []).some((r) => roles.has(r))) picked.add(u.id)
    })
  }

  if (selection.positions.length) {
    const positions = new Set(selection.positions)
    users.forEach((u) => {
      if (u.positionId && positions.has(u.positionId)) picked.add(u.id)
    })
  }

  selection.users.forEach((id) => picked.add(id))
  return [...picked]
}

/** 某人员被哪些来源维度覆盖（用于「来源」标签） */
export function sourcesOfUser(
  userId: string,
  selection: ScopeSelection,
  tree: OrgNodeLike[],
  users: UserLike[]
): string[] {
  const user = users.find((u) => u.id === userId)
  if (!user) return []

  const tags: string[] = []

  if (user.orgId && selection.orgs.some((orgId) => orgIdsUnder(tree, orgId).includes(user.orgId!))) {
    tags.push('组织')
  }
  if (user.positionId && selection.positions.includes(user.positionId)) tags.push('岗位')
  if ((user.roles ?? []).some((r) => selection.roles.includes(r))) tags.push('角色')
  if (selection.users.includes(userId)) tags.push('直接添加')

  return tags
}
