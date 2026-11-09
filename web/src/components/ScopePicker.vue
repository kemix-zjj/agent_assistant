<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getOrgTree, getPositions, getRoles, searchUsers } from '@/api'
import { expandUserIds, sourcesOfUser } from '@/utils/scopeExpand'
import type { OrgNodeLike, UserLike } from '@/utils/scopeExpand'
import type { ScopeDim, ScopePayload, ScopeMode } from '@/types/scope'

/**
 * 共享范围选择器（需求 4.0）：四处场景共用同一套组件
 * ① 创建向导共享设置 ② 共享提交弹窗 ③ 已共享助理范围弹窗 ④ 审批详情范围调整
 *
 * 交互对齐 prototype（common.js ScopeTransfer）：
 * 按页签先做批量选择 → 组织 / 角色 / 岗位展开出的人员自动带入「按人员」→
 * 每个页签均为「左侧可选 / 中间转移按钮 / 右侧已选」，最终生效颗粒是人。
 */
const props = withDefaults(
  defineProps<{
    modelValue: ScopePayload
    disabled?: boolean
    /** 是否在页签计数中展示上限（n/max）；共享提交场景展示，范围弹窗只展示 n */
    showLimits?: boolean
    /** 穿梭框上方说明文案，缺省使用默认文案 */
    tip?: string
  }>(),
  { disabled: false, showLimits: false, tip: '' }
)

const emit = defineEmits<{ 'update:modelValue': [value: ScopePayload] }>()

const LIMITS: Record<ScopeDim, number> = { org: 50, role: 50, position: 50, user: 200 }

const DIMS: Array<{ key: ScopeDim; label: string }> = [
  { key: 'org', label: '按组织' },
  { key: 'role', label: '按角色' },
  { key: 'position', label: '按岗位' },
  { key: 'user', label: '按人员' }
]

const scopeMode = ref<ScopeMode>(props.modelValue.scopeMode)
const activeDim = ref<ScopeDim>('org')
const keyword = ref('')
const loading = ref(false)

/** 来源维度选择态（组织 / 岗位 / 角色） */
const srcSel = ref<Record<'org' | 'role' | 'position', string[]>>({
  org: [...props.modelValue.orgs],
  role: [...props.modelValue.roles],
  position: [...props.modelValue.positions]
})

/** 单独添加的人员（不来自任何来源维度） */
const manual = ref<string[]>([...props.modelValue.users])

/** 从来源带入后被显式移除的人员 */
const excluded = ref<string[]>([])

/** 左侧勾选态（仅当前页签） */
const leftChecked = ref<string[]>([])
const leftAllChecked = ref(false)

/* ---------------- 主数据 ---------------- */

const orgNodes = ref<OrgNodeLike[]>([])
const roleList = ref<Array<{ id: string; name: string; desc?: string }>>([])
const positionList = ref<Array<{ id: string; name: string; desc?: string }>>([])
const userList = ref<Array<UserLike & { deptName?: string; jobNo?: string }>>([])

const NAME_MAP = ref<Record<ScopeDim, Map<string, string>>>({
  org: new Map(),
  role: new Map(),
  position: new Map(),
  user: new Map()
})
const DEPT_MAP = ref<Map<string, string>>(new Map())

async function loadBase(): Promise<void> {
  loading.value = true
  try {
    const [orgRes, roleRes, posRes, userRes] = await Promise.all([
      getOrgTree(),
      getRoles(),
      getPositions(),
      searchUsers({})
    ])
    orgNodes.value = orgRes.tree
    roleList.value = roleRes.list
    positionList.value = posRes.list
    userList.value = userRes.list

    NAME_MAP.value.org.clear()
    const walk = (nodes: OrgNodeLike[]): void => {
      nodes.forEach((n) => {
        NAME_MAP.value.org.set(n.id, n.name)
        if (n.children) walk(n.children)
      })
    }
    walk(orgRes.tree)
    roleRes.list.forEach((r) => NAME_MAP.value.role.set(r.id, r.name))
    posRes.list.forEach((p) => NAME_MAP.value.position.set(p.id, p.name))
    userRes.list.forEach((u) => {
      NAME_MAP.value.user.set(u.id, u.name)
      if (u.deptName) DEPT_MAP.value.set(u.id, u.deptName)
    })
  } catch {
    ElMessage.error('组织或人员数据加载失败，点击重试')
  } finally {
    loading.value = false
  }
}

onMounted(loadBase)

/* ---------------- 计算 ---------------- */

function toPayload(): ScopePayload {
  return {
    scopeMode: scopeMode.value,
    orgs: [...srcSel.value.org],
    roles: [...srcSel.value.role],
    positions: [...srcSel.value.position],
    users: [...manual.value]
  }
}

/** 来源维度（组织含下级 / 角色 / 岗位）展开出的人员，不含直接添加 */
const derivedIds = computed(() =>
  expandUserIds(
    {
      orgs: srcSel.value.org,
      roles: srcSel.value.role,
      positions: srcSel.value.position,
      users: []
    },
    orgNodes.value,
    userList.value
  )
)

/** 单独添加且不来自任何来源维度的人员 */
const manualOnlyIds = computed(() => manual.value.filter((id) => !derivedIds.value.includes(id)))

/** 生效授权人员 = 来源展开 ∪ 单独添加 − 显式移除 */
const effectiveIds = computed(() => {
  const out = new Set<string>()
  derivedIds.value.forEach((id) => {
    if (!excluded.value.includes(id)) out.add(id)
  })
  manualOnlyIds.value.forEach((id) => {
    if (!excluded.value.includes(id)) out.add(id)
  })
  return [...out]
})

/** 来源变化后，清理已无来源的显式移除记录 */
watch(derivedIds, (next) => {
  excluded.value = excluded.value.filter((id) => next.includes(id))
})

/** 当前页签的已选集合 */
const selectedIds = computed<string[]>(() => {
  if (activeDim.value === 'user') return effectiveIds.value
  return srcSel.value[activeDim.value]
})

function flatOrgs(nodes: OrgNodeLike[], level = 0): Array<{ id: string; name: string; level: number; meta?: string }> {
  const out: Array<{ id: string; name: string; level: number; meta?: string }> = []
  nodes.forEach((n) => {
    out.push({ id: n.id, name: n.name, level, meta: level === 0 ? '组织' : '' })
    if (n.children) out.push(...flatOrgs(n.children, level + 1))
  })
  return out
}

/** 当前页签的全部可选项 */
const allItems = computed<Array<{ id: string; name: string; level?: number; meta?: string }>>(() => {
  if (activeDim.value === 'org') return flatOrgs(orgNodes.value)
  if (activeDim.value === 'role') return roleList.value.map((r) => ({ id: r.id, name: r.name, meta: r.desc }))
  if (activeDim.value === 'position') return positionList.value.map((p) => ({ id: p.id, name: p.name, meta: p.desc }))
  return userList.value.map((u) => ({ id: u.id, name: u.name, meta: u.deptName }))
})

const leftItems = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return allItems.value
    .filter((it) => !selectedIds.value.includes(it.id))
    .filter((it) => !kw || `${it.name} ${it.meta ?? ''}`.toLowerCase().includes(kw))
})

const rightItems = computed(() => allItems.value.filter((it) => selectedIds.value.includes(it.id)))

/** 已选人员身上的来源标签（组织 / 角色 / 岗位 / 直接添加） */
function srcTagsOf(userId: string): string[] {
  return sourcesOfUser(
    userId,
    {
      orgs: srcSel.value.org,
      roles: srcSel.value.role,
      positions: srcSel.value.position,
      users: manual.value
    },
    orgNodes.value,
    userList.value
  )
}

/** 底部汇总 */
const summaryText = computed(() => {
  const src: string[] = []
  if (srcSel.value.org.length) src.push(`组织 ${srcSel.value.org.length}`)
  if (srcSel.value.role.length) src.push(`角色 ${srcSel.value.role.length}`)
  if (srcSel.value.position.length) src.push(`岗位 ${srcSel.value.position.length}`)
  if (manualOnlyIds.value.length) src.push(`单独添加 ${manualOnlyIds.value.length}`)
  return { people: effectiveIds.value.length, src, excluded: excluded.value.length }
})

/** 预览 chips：来源（虚线）+ 生效人员（实线） */
const previewChips = computed(() => {
  const srcChips: Array<{ dim: 'org' | 'role' | 'position'; id: string; label: string }> = [
    ...srcSel.value.org.map((id) => ({ dim: 'org' as const, id, label: `组织 · ${NAME_MAP.value.org.get(id) ?? id}` })),
    ...srcSel.value.role.map((id) => ({ dim: 'role' as const, id, label: `角色 · ${NAME_MAP.value.role.get(id) ?? id}` })),
    ...srcSel.value.position.map((id) => ({ dim: 'position' as const, id, label: `岗位 · ${NAME_MAP.value.position.get(id) ?? id}` }))
  ]
  const userChips = effectiveIds.value.map((id) => ({
    id,
    label: NAME_MAP.value.user.get(id) ?? id,
    meta: DEPT_MAP.value.get(id) ?? ''
  }))
  return { srcChips, userChips }
})

/** 页签计数：人员取生效人数，其余取来源选择数 */
function dimCount(key: ScopeDim): number {
  if (key === 'user') return effectiveIds.value.length
  return srcSel.value[key].length
}

const dimLabel = computed(() => DIMS.find((d) => d.key === activeDim.value)?.label.replace('按', '') ?? '')

const hintText = computed(() =>
  activeDim.value === 'user'
    ? '右侧为最终生效的授权人员；在此移出的人员，即使所属组织 / 角色 / 岗位仍在授权范围内，也不再对其生效。'
    : `在左侧勾选后点击 › 移入右侧；所选${dimLabel.value}下的人员会自动带入「按人员」，可在人员页签继续增删。`
)

/* ---------------- 交互 ---------------- */

function switchDim(key: ScopeDim): void {
  activeDim.value = key
  keyword.value = ''
  leftChecked.value = []
  leftAllChecked.value = false
}

function toggleLeftCheck(id: string): void {
  const i = leftChecked.value.indexOf(id)
  if (i >= 0) leftChecked.value.splice(i, 1)
  else leftChecked.value.push(id)
  leftAllChecked.value = leftItems.value.length > 0 && leftChecked.value.length === leftItems.value.length
}

function toggleLeftAll(): void {
  leftAllChecked.value = !leftAllChecked.value
  leftChecked.value = leftAllChecked.value ? leftItems.value.map((it) => it.id) : []
}

/** 上限校验：超出部分丢弃并提示 */
function fitLimit(ids: string[]): string[] {
  const max = LIMITS[activeDim.value]
  const unit = activeDim.value === 'user' ? ' 人' : ' 项'
  const left = max - selectedIds.value.length
  if (left <= 0) {
    ElMessage.error(`按${dimLabel.value}最多 ${max}${unit}，请先移出部分已选项`)
    return []
  }
  if (ids.length > left) {
    ElMessage.error(`按${dimLabel.value}最多 ${max}${unit}，本次仅移入 ${left}${unit}`)
    return ids.slice(0, left)
  }
  return ids
}

/** 移入：来源维度记录选择；人员维度记为单独添加 */
function addIds(ids: string[]): void {
  ids.forEach((id) => {
    if (activeDim.value === 'user') {
      if (!manual.value.includes(id)) manual.value.push(id)
      excluded.value = excluded.value.filter((x) => x !== id)
    } else if (!srcSel.value[activeDim.value].includes(id)) {
      srcSel.value[activeDim.value].push(id)
    }
  })
}

/** 移出操作 */
function removeIds(ids: string[]): void {
  ids.forEach((id) => {
    if (activeDim.value === 'user') {
      if (manual.value.includes(id) && !derivedIds.value.includes(id)) {
        // 单独添加的人员：直接移除
        manual.value = manual.value.filter((x) => x !== id)
      } else if (derivedIds.value.includes(id)) {
        // 来源带入的人员：记为显式移除
        if (!excluded.value.includes(id)) excluded.value.push(id)
      }
    } else {
      srcSel.value[activeDim.value] = srcSel.value[activeDim.value].filter((x) => x !== id)
    }
  })
}

function moveSelected(): void {
  const ids = fitLimit([...leftChecked.value])
  addIds(ids)
  leftChecked.value = []
  leftAllChecked.value = false
}

function moveAll(): void {
  const ids = fitLimit(leftItems.value.map((it) => it.id))
  addIds(ids)
  leftChecked.value = []
  leftAllChecked.value = false
}

function moveBackSelected(): void {
  const ids = rightItems.value.map((it) => it.id).filter((id) => leftChecked.value.includes(id))
  removeIds(ids.length ? ids : [])
}

function moveBackAll(): void {
  removeIds(rightItems.value.map((it) => it.id))
}

function removeOne(id: string): void {
  removeIds([id])
}

function clearRight(): void {
  removeIds(rightItems.value.map((it) => it.id))
}

/** 预览区移除：来源 chip 移除对应维度项 */
function removePreviewSrc(kind: 'org' | 'role' | 'position', id: string): void {
  srcSel.value[kind] = srcSel.value[kind].filter((x) => x !== id)
}

/* ---------------- 同步 ---------------- */

function samePayload(a: ScopePayload, b: ScopePayload): boolean {
  const eq = (x: string[], y: string[]): boolean => x.length === y.length && x.every((v, i) => v === y[i])
  return (
    a.scopeMode === b.scopeMode &&
    eq(a.orgs, b.orgs) &&
    eq(a.roles, b.roles) &&
    eq(a.positions, b.positions) &&
    eq(a.users, b.users)
  )
}

// 内部 → 外部：值有变化才 emit，避免与父组件回写形成循环
watch(
  [scopeMode, srcSel, manual],
  () => {
    const next = toPayload()
    if (!samePayload(next, props.modelValue)) emit('update:modelValue', next)
  },
  { deep: true }
)

// 外部 → 内部：仅当外部值与当前不一致时回写，避免覆盖用户正在进行的操作
watch(
  () => props.modelValue,
  (v) => {
    if (samePayload(v, toPayload())) return
    srcSel.value = { org: [...v.orgs], role: [...v.roles], position: [...v.positions] }
    manual.value = [...v.users]
    scopeMode.value = v.scopeMode
  },
  { deep: true }
)

const rangeEmpty = computed(
  () => scopeMode.value === 'RANGE' && effectiveIds.value.length === 0
)

defineExpose({ rangeEmpty, totalCount: computed(() => effectiveIds.value.length) })
</script>

<template>
  <div class="scope-picker" :class="{ 'is-disabled': disabled }">
    <el-radio-group v-model="scopeMode" :disabled="disabled" class="scope-mode">
      <el-radio value="RANGE">范围授权</el-radio>
      <el-radio value="PUBLIC">公开</el-radio>
    </el-radio-group>

    <div class="scope-mode-hint">「范围授权」需指定可用的组织、角色、岗位或人员；「公开」全公司可用，无需选择范围。</div>

    <div v-if="scopeMode === 'PUBLIC'" class="public-tip">公开 · 全公司可用，无需选择范围</div>

    <template v-else>
      <div class="tf-tip">{{ tip || '按页签先做批量选择：组织、角色、岗位会把人展开带进「按人员」，最终生效颗粒是人员，可在人员页签继续增删。' }}</div>

      <div v-loading="loading" class="tf">
        <!-- 页签 -->
        <div class="tf-tabs">
          <div
            v-for="d in DIMS"
            :key="d.key"
            class="tf-tab"
            :class="{ active: activeDim === d.key }"
            @click="switchDim(d.key)"
          >
            {{ d.label }}
            <span class="tf-tab-count" :class="{ has: dimCount(d.key) > 0 }">
              {{ showLimits ? `${dimCount(d.key)}/${LIMITS[d.key]}` : dimCount(d.key) }}
            </span>
          </div>
        </div>

        <!-- 维度语义提示 -->
        <div class="tf-hint">{{ hintText }}</div>

        <!-- 穿梭区 -->
        <div class="tf-body">
          <!-- 左：可选 -->
          <div class="tf-panel">
            <div class="tf-panel-head">
              <label class="tf-check-all" @click.prevent="toggleLeftAll">
                <el-checkbox :model-value="leftAllChecked" class="tf-cb" />
                <span>全选</span>
              </label>
              <span>可选 <b class="tf-num">{{ leftItems.length }}</b> 项</span>
            </div>
            <div class="tf-search">
              <el-input v-model="keyword" size="small" placeholder="搜索名称 / 部门" clearable />
            </div>
            <div class="tf-list">
              <label
                v-for="it in leftItems"
                :key="it.id"
                class="tf-row"
                @click.prevent="toggleLeftCheck(it.id)"
              >
                <el-checkbox :model-value="leftChecked.includes(it.id)" class="tf-cb" />
                <span class="tf-name" :style="{ paddingLeft: `${(it.level ?? 0) * 14}px` }">{{ it.name }}</span>
                <span v-if="it.meta" class="tf-meta">{{ it.meta }}</span>
              </label>
              <div v-if="!leftItems.length" class="tf-empty">{{ keyword ? '没有匹配项' : '无可选项' }}</div>
            </div>
          </div>

          <!-- 中：转移按钮 -->
          <div class="tf-ops">
            <button type="button" class="tf-btn tf-btn-primary" title="移入已选" @click="moveSelected">›</button>
            <button type="button" class="tf-btn tf-btn-primary" title="全部移入" @click="moveAll">»</button>
            <button type="button" class="tf-btn" title="移出已选" @click="moveBackSelected">‹</button>
            <button type="button" class="tf-btn" title="全部移出" @click="moveBackAll">«</button>
          </div>

          <!-- 右：已选 -->
          <div class="tf-panel">
            <div class="tf-panel-head">
              <span>已选 <b class="tf-num">{{ rightItems.length }}</b> 项</span>
              <span class="tf-clear" @click="clearRight">清空</span>
            </div>
            <div class="tf-search tf-search-hidden" />
            <div class="tf-list">
              <div
                v-for="it in rightItems"
                :key="it.id"
                class="tf-row"
                @click.prevent="toggleLeftCheck(it.id)"
              >
                <el-checkbox :model-value="leftChecked.includes(it.id)" class="tf-cb" />
                <span class="tf-name">{{ it.name }}</span>
                <template v-if="activeDim === 'user'">
                  <span v-for="t in srcTagsOf(it.id)" :key="t" class="tf-src">{{ t }}</span>
                </template>
                <span v-if="it.meta" class="tf-meta">{{ it.meta }}</span>
                <span class="tf-del" title="移出" @click.stop="removeOne(it.id)">×</span>
              </div>
              <div v-if="!rightItems.length" class="tf-empty">
                {{ activeDim === 'user' ? '暂无授权人员' : '暂无已选项' }}
              </div>
            </div>
          </div>
        </div>

        <!-- 汇总 -->
        <div class="tf-summary">
          生效授权 <b class="tf-num">{{ summaryText.people }}</b> 人
          <template v-if="summaryText.src.length"> · 来源：{{ summaryText.src.join(' · ') }}</template>
          <template v-if="summaryText.excluded"> · 已单独移除 <b class="tf-num">{{ summaryText.excluded }}</b> 人</template>
        </div>
      </div>

      <!-- 授权范围预览 -->
      <div class="scope-block">
        <div class="scope-block-title">授权范围预览</div>
        <div class="scope-chips">
          <span v-for="c in previewChips.srcChips" :key="`${c.dim}-${c.id}`" class="scope-chip scope-chip-src">
            {{ c.label }}
            <span class="x" @click="removePreviewSrc(c.dim, c.id)">×</span>
          </span>
          <span v-for="c in previewChips.userChips" :key="`u-${c.id}`" class="scope-chip">
            {{ c.label }}<span v-if="c.meta" class="scope-chip-meta">{{ c.meta }}</span>
          </span>
        </div>
        <div v-if="!previewChips.srcChips.length && !previewChips.userChips.length" class="scope-empty">
          尚未选择授权对象，请至少选择一个组织或人员
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.scope-picker {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scope-mode {
  padding-left: 2px;
}

.scope-mode-hint {
  font-size: 12px;
  line-height: 1.6;
  color: var(--at-text-weak);
}

.public-tip {
  padding: 20px;
  background: #f7f8fa;
  border-radius: 4px;
  color: var(--at-text-sub);
  text-align: center;
}

.tf-tip {
  font-size: 12px;
  line-height: 1.6;
  color: var(--at-text-sub);
}

/* ---------- 穿梭框 ---------- */
.tf {
  border: 1px solid var(--at-border);
  border-radius: 4px;
  background: #fff;
  overflow: hidden;
}

.tf-tabs {
  display: flex;
  gap: 20px;
  padding: 0 12px;
  border-bottom: 1px solid #ebedf0;
}

.tf-tab {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 38px;
  font-size: 13px;
  color: var(--at-text);
  cursor: pointer;
  transition: color 0.15s;
}

.tf-tab:hover {
  color: var(--at-brand);
}

.tf-tab.active {
  color: var(--at-brand);
  font-weight: 600;
}

.tf-tab.active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 2px;
  background: var(--at-brand);
  border-radius: 1px;
}

.tf-tab-count {
  min-width: 16px;
  height: 16px;
  line-height: 16px;
  padding: 0 4px;
  font-size: 11px;
  text-align: center;
  color: var(--at-text-sub);
  background: #f4f7f9;
  border-radius: 3px;
}

.tf-tab-count.has {
  color: var(--at-brand);
  background: #eef4ff;
}

.tf-hint {
  position: relative;
  padding: 8px 12px 8px 24px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--at-text-weak);
  background: #f9fafb;
  border-bottom: 1px solid #ebedf0;
}

.tf-hint::before {
  content: '';
  position: absolute;
  left: 12px;
  top: 50%;
  width: 4px;
  height: 4px;
  margin-top: -2px;
  border-radius: 50%;
  background: var(--at-brand);
}

.tf-body {
  display: flex;
  gap: 8px;
  padding: 12px;
}

.tf-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 248px;
  border: 1px solid #ebedf0;
  border-radius: 4px;
  background: #fff;
  overflow: hidden;
}

.tf-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 0 0 36px;
  padding: 0 10px;
  background: #f4f7f9;
  border-bottom: 1px solid #ebedf0;
  font-size: 12px;
  color: var(--at-text-sub);
}

.tf-check-all {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--at-text);
  cursor: pointer;
}

.tf-cb {
  pointer-events: none;
  height: auto;
}

.tf-num {
  font-style: normal;
  font-weight: 600;
  color: var(--at-brand);
}

.tf-clear {
  font-size: 12px;
  color: var(--at-brand);
  cursor: pointer;
}

.tf-search {
  padding: 8px 10px 0;
}

.tf-search-hidden {
  height: 8px;
  padding: 0;
}

.tf-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 0;
}

.tf-row {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 32px;
  padding: 0 10px;
  cursor: pointer;
  transition: background 0.15s;
}

.tf-row:hover {
  background: #f5f7fa;
}

.tf-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--at-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tf-meta {
  flex: 0 1 auto;
  max-width: 45%;
  font-size: 11px;
  color: var(--at-text-weak);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tf-src {
  flex: 0 0 auto;
  padding: 0 4px;
  height: 18px;
  line-height: 18px;
  font-size: 11px;
  color: var(--at-brand);
  background: #eef4ff;
  border-radius: 3px;
}

.tf-del {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  color: var(--at-text-weak);
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
}

.tf-del:hover {
  color: var(--at-danger);
}

.tf-empty {
  padding: 24px 0;
  text-align: center;
  font-size: 12px;
  color: var(--at-text-weak);
}

.tf-ops {
  flex: 0 0 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.tf-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  font-size: 16px;
  line-height: 1;
  color: var(--at-text-sub);
  background: #fff;
  border: 1px solid var(--at-border);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}

.tf-btn:hover {
  border-color: var(--at-brand);
  color: var(--at-brand);
}

.tf-btn-primary {
  color: #fff;
  background: var(--at-brand);
  border-color: var(--at-brand);
}

.tf-btn-primary:hover {
  color: #fff;
  background: #2468f2;
  border-color: #2468f2;
}

.tf-summary {
  padding: 0 12px 12px;
  font-size: 12px;
  color: var(--at-text-sub);
}

/* ---------- 预览 ---------- */
.scope-block {
  padding: 12px;
  background: #f9fafb;
  border-radius: 4px;
}

.scope-block-title {
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--at-text);
}

.scope-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.scope-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  font-size: 12px;
  color: #2563c9;
  background: #eef4ff;
  border: 1px solid #d6e4ff;
  border-radius: 3px;
}

.scope-chip-src {
  color: var(--at-text-sub);
  background: #f4f7f9;
  border: 1px dashed var(--at-border);
}

.scope-chip .x {
  cursor: pointer;
  color: var(--at-text-sub);
  line-height: 1;
}

.scope-chip-meta {
  margin-left: 4px;
  font-size: 11px;
  color: var(--at-text-weak);
}

.scope-empty {
  font-size: 12px;
  color: var(--at-text-weak);
}

.is-disabled {
  opacity: 0.9;
}
</style>
