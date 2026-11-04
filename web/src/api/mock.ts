/**
 * Mock 数据层：在后端就绪前提供与 docs/03-接口设计 一致的响应结构。
 * 仅内存存储（刷新页面重置），用于页面评审与交互验证。
 */
import type {
  CategoryItem,
  DeleteImpact,
  AssistantCard,
  AssistantDetail,
  AssistantUpsertPayload,
  KnowledgeBaseItem,
  McpItem,
  ShareSubmitPayload,
  SkillItem,
  SummonResult
} from '@/types/assistant'
import type { ApprovalCard, ApprovalDecisionResult, ApprovalDetail } from '@/types/approval'
import type { Scope, ScopeDim, ScopePayload } from '@/types/scope'
import { ApiError } from '@/types/api'

/* ============================ 字典 ============================ */

export const CATEGORIES: CategoryItem[] = [
  { categoryId: 1, name: '协同办公', isBuiltin: true, sortNo: 10 },
  { categoryId: 2, name: '人资', isBuiltin: true, sortNo: 20 },
  { categoryId: 3, name: '智慧云仓', isBuiltin: true, sortNo: 30 },
  { categoryId: 4, name: '环安', isBuiltin: true, sortNo: 40 },
  { categoryId: 5, name: '经营管理', isBuiltin: true, sortNo: 50 }
]

export const SKILLS: SkillItem[] = [
  { id: 's1', name: '简历初筛', desc: '按岗位画像对候选人简历打分并输出匹配结论', market: 'internal' },
  { id: 's2', name: '面试提纲生成', desc: '依据岗位胜任力模型生成结构化面试题', market: 'internal' },
  { id: 's3', name: '薪资结构解析', desc: '拆解工资条结构并定位异常项', market: 'internal' },
  { id: 's4', name: '制度条款检索', desc: '按问题检索制度原文并给出来源条款', market: 'internal' },
  { id: 's5', name: '巡检清单生成', desc: '按厂区与设备类型生成巡检项清单', market: 'internal' },
  { id: 's6', name: '会议纪要提炼', desc: '从会议记录中提炼结论、待办与责任人', market: 'external' },
  { id: 's7', name: '报价单校验', desc: '按价格政策校验报价单合规性', market: 'external' },
  { id: 's8', name: '培训课件生成', desc: '按培训主题生成课件大纲与练习题', market: 'external' },
  { id: 's9', name: '表格数据处理', desc: '按指令完成表格清洗、汇总与图表建议', market: 'external' },
  { id: 's10', name: '日程会议安排', desc: '解析自然语言生成日程与会议邀请', market: 'external' }
]

export const MCPS: McpItem[] = [
  { id: 'm1', name: '企业微信通讯录', type: '组织数据', market: 'internal' },
  { id: 'm2', name: 'HR 主数据服务', type: '业务系统', market: 'internal' },
  { id: 'm3', name: '考勤打卡服务', type: '业务系统', market: 'internal' },
  { id: 'm4', name: '薪酬核算服务', type: '业务系统', market: 'internal' },
  { id: 'm5', name: 'WMS 仓储服务', type: '业务系统', market: 'external' },
  { id: 'm6', name: '隐患台账服务', type: '业务系统', market: 'external' },
  { id: 'm7', name: '飞书多维表格', type: '第三方应用', market: 'external' },
  { id: 'm8', name: '钉钉待办', type: '第三方应用', market: 'external' }
]

export const KNOWLEDGE_BASES: KnowledgeBaseItem[] = [
  {
    id: 'k1', name: '招聘管理制度库', documentCount: 128, market: 'internal',
    files: ['招聘管理办法.pdf', '面试评估操作指引.docx', '校园招聘流程.pdf']
  },
  {
    id: 'k2', name: '薪酬福利政策库', documentCount: 96, market: 'internal',
    files: ['薪酬结构管理办法.pdf', '个税专项附加扣除指引.pdf', '社保公积金缴纳标准.xlsx']
  },
  {
    id: 'k3', name: '员工考勤制度库', documentCount: 64, market: 'internal',
    files: ['考勤管理制度.pdf', '请假与调休细则.docx', '加班管理规定.pdf']
  },
  {
    id: 'k4', name: '仓储作业规范库', documentCount: 212, market: 'internal',
    files: ['仓储盘点作业指导书.pdf', '库区安全管理规范.pdf', '出入库操作手册.docx']
  },
  {
    id: 'k5', name: '环安法规与标准库', documentCount: 158, market: 'internal',
    files: ['安全生产法（2021）.pdf', '隐患排查治理标准.docx', '环保合规清单.xlsx']
  },
  {
    id: 'k6', name: '报价政策库', documentCount: 43, market: 'internal',
    files: ['价格政策管理办法.pdf', '折扣审批权限表.xlsx']
  }
]

/** 组织树（外部主数据，仅演示） */
export interface OrgNode {
  id: string
  name: string
  level: number
  children?: OrgNode[]
}

export const ORG_TREE: OrgNode[] = [
  {
    id: 'O1',
    name: '九牧集团有限公司',
    level: 1,
    children: [
      {
        id: 'O11',
        name: '人力资源部',
        level: 2,
        children: [
          { id: 'O111', name: '招聘组', level: 3 },
          { id: 'O112', name: '薪酬绩效组', level: 3 }
        ]
      },
      {
        id: 'O12',
        name: '智慧云仓事业部',
        level: 2,
        children: [
          { id: 'O121', name: '仓储运营部', level: 3 },
          { id: 'O122', name: '物流调度部', level: 3 }
        ]
      },
      { id: 'O13', name: '环安管理部', level: 2 },
      {
        id: 'O14',
        name: '经营管理中心',
        level: 2,
        children: [{ id: 'O141', name: '报价管理组', level: 3 }]
      }
    ]
  }
]

export const ROLES = [
  { id: 'r1', name: '招聘专员', desc: '负责简历筛选与面试安排' },
  { id: 'r2', name: '薪酬专员', desc: '负责薪资核算与个税申报' },
  { id: 'r3', name: '仓储主管', desc: '负责库区作业与盘点管理' },
  { id: 'r4', name: '环安工程师', desc: '负责隐患排查与合规检查' }
]

export const POSITIONS = [
  { id: 'p1', name: '专员', desc: '专业序列' },
  { id: 'p2', name: '主管', desc: '基层管理' },
  { id: 'p3', name: '经理', desc: '中层管理' }
]

export const USERS = [
  { id: 'u1', name: '李静', deptName: '人力资源部 · 招聘组', jobNo: 'E0231', orgId: 'O111', roles: ['r1'], positionId: 'p1' },
  { id: 'u2', name: '林晓', deptName: '人力资源部 · 薪酬绩效组', jobNo: 'E0187', orgId: 'O112', roles: ['r2'], positionId: 'p1' },
  { id: 'u3', name: '陈志远', deptName: '智慧云仓事业部 · 仓储运营部', jobNo: 'E0342', orgId: 'O121', roles: ['r3'], positionId: 'p2' },
  { id: 'u4', name: '赵敏', deptName: '环安管理部', jobNo: 'E0092', orgId: 'O13', roles: ['r4'], positionId: 'p1' },
  { id: 'u5', name: '周涛', deptName: '经营管理中心 · 报价管理组', jobNo: 'E0512', orgId: 'O141', roles: [], positionId: 'p3' },
  { id: 'u6', name: '吴磊', deptName: '智慧云仓事业部 · 物流调度部', jobNo: 'E0288', orgId: 'O122', roles: [], positionId: 'p1' }
]

/** 组织节点自身 + 全部下级节点 id（与原型 orgIdsUnder 一致） */
export function orgIdsUnder(orgId: string): string[] {
  const out: string[] = []
  const collect = (node: OrgNode): void => {
    out.push(node.id)
    ;(node.children ?? []).forEach(collect)
  }
  const walk = (nodes: OrgNode[]): void => {
    nodes.forEach((n) => {
      if (n.id === orgId) collect(n)
      else if (n.children) walk(n.children)
    })
  }
  walk(ORG_TREE)
  return out
}

/** 来源维度展开出的人员（组织含下级 / 岗位 / 角色） */
export function derivedUserIds(payload: ScopePayload): string[] {
  const picked = new Set<string>()
  payload.orgs.forEach((oid) => {
    const sub = orgIdsUnder(oid)
    USERS.forEach((u) => {
      if (sub.includes(u.orgId)) picked.add(u.id)
    })
  })
  payload.positions.forEach((pid) => {
    USERS.forEach((u) => {
      if (u.positionId === pid) picked.add(u.id)
    })
  })
  payload.roles.forEach((rid) => {
    USERS.forEach((u) => {
      if (u.roles.includes(rid)) picked.add(u.id)
    })
  })
  return [...picked]
}

/** 某人员被哪些来源维度覆盖（组织 / 岗位 / 角色 / 直接添加） */
export function sourcesOf(userId: string, payload: ScopePayload): string[] {
  const u = USERS.find((x) => x.id === userId)
  if (!u) return []
  const tags: string[] = []
  if (payload.orgs.some((oid) => orgIdsUnder(oid).includes(u.orgId))) tags.push('组织')
  if (payload.positions.some((pid) => pid === u.positionId)) tags.push('岗位')
  if (payload.roles.some((rid) => u.roles.includes(rid))) tags.push('角色')
  if (payload.users.includes(userId)) tags.push('直接添加')
  return tags
}

/* ============================ 助理种子数据 ============================ */

interface AssistantRow extends Omit<AssistantDetail, 'categoryName'> {
  categoryId: number
}

function catName(id: number): string {
  return CATEGORIES.find((c) => c.categoryId === id)?.name ?? '未分类'
}

const nowStr = (): string => {
  const d = new Date()
  const p = (n: number): string => (n < 10 ? `0${n}` : String(n))
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

function skillOf(ids: string[]): SkillItem[] {
  return ids.map((id) => SKILLS.find((s) => s.id === id)).filter((s): s is SkillItem => !!s)
}
function mcpOf(ids: string[]): McpItem[] {
  return ids.map((id) => MCPS.find((m) => m.id === id)).filter((m): m is McpItem => !!m)
}
function kbOf(ids: string[]): KnowledgeBaseItem[] {
  return ids.map((id) => KNOWLEDGE_BASES.find((k) => k.id === id)).filter((k): k is KnowledgeBaseItem => !!k)
}

const PROMPT_TPL = (role: string, scope: string): string =>
  `你是九牧集团人力资源部的${role}，负责回答员工关于${scope}的问题。\n` +
  '回答要求：先给结论，再给制度依据，涉及个人数据时须提示员工自行核对；\n' +
  '无法确认的问题必须说明「需人工确认」，不得编造条款编号。'

let ASSISTANT_SEQ = 10000

export const assistants: AssistantRow[] = [
  {
    assistantId: 1001,
    name: '招聘面试助理',
    avatarType: 'char',
    avatarChar: '招',
    avatarUrl: null,
    avatarColor: '#3685F2',
    description: '面向候选人与面试官的双向问答助理，可生成面试提纲、评估维度与面评意见，并解释招聘制度条款。',
    tags: ['招聘', '面试', '校招'],
    categoryId: 2,
    source: 'custom',
    shareStatus: 'approved',
    version: 'v1.2',
    ownerName: '王晓明',
    ownerDeptName: '人力资源部 · 招聘组',
    createdAt: '2026-10-18 09:24:00',
    updatedAt: '2026-10-23 16:40:00',
    prompt: PROMPT_TPL('招聘面试助理', '招聘流程、面试评估与录用规则'),
    skills: skillOf(['s1', 's2', 's4']),
    mcps: mcpOf(['m1', 'm2']),
    knowledgeBases: kbOf(['k1']),
    quickQuestions: ['校招面试提问清单怎么设计？', '如何评估候选人的稳定性？', '录用审批需要准备哪些材料？'],
    shareScope: {
      scopeMode: 'RANGE',
      orgs: [{ id: 'O11', name: '人力资源部' }],
      roles: [],
      positions: [],
      users: [
        { id: 'u1', name: '李静', deptName: '人力资源部 · 招聘组' },
        { id: 'u2', name: '林晓', deptName: '人力资源部 · 薪酬绩效组' },
        { id: 'u5', name: '周涛', deptName: '经营管理中心 · 报价管理组' }
      ],
      grantTotal: 3,
      summary: '人力资源部、周涛 等 3 人'
    },
    versionHistory: [
      { version: 'v1.2', action: 'update', actionName: '编辑更新', operatorName: '王晓明', remark: '补充校招场景提示词', createdAt: '2026-10-23 16:40:00' },
      { version: 'v1.1', action: 'scope_change', actionName: '授权范围变更', operatorName: '王建国', remark: '新增薪酬绩效组（林晓）', createdAt: '2026-10-21 10:12:00' },
      { version: 'v1.0', action: 'create', actionName: '创建', operatorName: '王晓明', remark: '手动创建', createdAt: '2026-10-18 09:24:00' }
    ]
  },
  {
    assistantId: 1002,
    name: '薪酬核算助理',
    avatarType: 'char',
    avatarChar: '薪',
    avatarUrl: null,
    avatarColor: '#04D999',
    description: '按月解释薪资结构与个税口径，核对薪资异常项并给出调整建议，支持按部门维度汇总。',
    tags: ['薪酬', '核算'],
    categoryId: 2,
    source: 'custom',
    shareStatus: 'approved',
    version: 'v1.0',
    ownerName: '王晓明',
    ownerDeptName: '人力资源部 · 招聘组',
    createdAt: '2026-10-15 14:02:00',
    updatedAt: '2026-10-22 10:08:00',
    prompt: PROMPT_TPL('薪酬核算助理', '薪资结构、个税与社保公积金口径'),
    skills: skillOf(['s3', 's4']),
    mcps: mcpOf(['m2', 'm4']),
    knowledgeBases: kbOf(['k2']),
    quickQuestions: ['本月薪资异常项怎么核对？', '个税专项附加扣除怎么处理？'],
    shareScope: {
      scopeMode: 'RANGE',
      orgs: [{ id: 'O1', name: '九牧集团有限公司' }],
      roles: [],
      positions: [],
      users: USERS.map((u) => ({ id: u.id, name: u.name, deptName: u.deptName })),
      grantTotal: USERS.length,
      summary: '九牧集团有限公司 等 6 人'
    },
    versionHistory: [
      { version: 'v1.0', action: 'create', actionName: '创建并共享', operatorName: '王晓明', remark: '手动创建，首次申请共享', createdAt: '2026-10-15 14:02:00' }
    ]
  },
  {
    assistantId: 1003,
    name: '考勤答疑助理',
    avatarType: 'char',
    avatarChar: '勤',
    avatarUrl: null,
    avatarColor: '#FF813B',
    description: '解答请假、调休、加班与补卡规则，可按制度条款给出依据，并提示需要走流程的场景。',
    tags: ['考勤', '制度'],
    categoryId: 2,
    source: 'custom',
    shareStatus: 'unshared',
    version: 'v1.0',
    ownerName: '王晓明',
    ownerDeptName: '人力资源部 · 招聘组',
    createdAt: '2026-10-21 11:16:00',
    updatedAt: '2026-10-21 11:16:00',
    prompt: PROMPT_TPL('考勤答疑助理', '请假、调休、加班与补卡规则'),
    skills: skillOf(['s4']),
    mcps: mcpOf(['m3']),
    knowledgeBases: kbOf(['k3']),
    quickQuestions: ['年假没休完怎么折算？', '补卡需要哪些审批？'],
    shareScope: null,
    versionHistory: [
      { version: 'v1.0', action: 'create', actionName: '创建', operatorName: '王晓明', remark: '手动创建', createdAt: '2026-10-21 11:16:00' }
    ]
  },
  {
    assistantId: 1004,
    name: '环安巡检助理',
    avatarType: 'char',
    avatarChar: '环',
    avatarUrl: null,
    avatarColor: '#FF4D5D',
    description: '输出车间巡检清单与隐患整改建议，可按厂区维度汇总隐患分布与整改完成率。',
    tags: ['环安', '巡检', '隐患'],
    categoryId: 4,
    source: 'custom',
    shareStatus: 'rejected',
    version: 'v1.1',
    ownerName: '王晓明',
    ownerDeptName: '人力资源部 · 招聘组',
    createdAt: '2026-10-19 16:30:00',
    updatedAt: '2026-10-24 15:02:00',
    prompt: PROMPT_TPL('环安巡检助理', '车间巡检标准与隐患整改要求'),
    skills: skillOf(['s5']),
    mcps: mcpOf(['m6']),
    knowledgeBases: kbOf(['k5']),
    quickQuestions: ['本月隐患整改率怎么算？', '巡检记录需要保留多久？'],
    shareScope: null,
    versionHistory: [
      { version: 'v1.1', action: 'update', actionName: '编辑更新', operatorName: '王晓明', remark: '补充隐患分级说明', createdAt: '2026-10-24 14:20:00' },
      { version: 'v1.0', action: 'create', actionName: '创建并共享', operatorName: '王晓明', remark: '手动创建，首次申请共享', createdAt: '2026-10-19 16:30:00' }
    ]
  },
  {
    assistantId: 1005,
    name: '员工手册问答助理',
    avatarType: 'char',
    avatarChar: '册',
    avatarUrl: null,
    avatarColor: '#5E9DF5',
    description: '基于最新版员工手册解答假期、福利与行为规范问题，并定位到具体章节条款。',
    tags: ['制度', '手册'],
    categoryId: 2,
    source: 'custom',
    shareStatus: 'pending',
    version: 'v1.0',
    ownerName: '王晓明',
    ownerDeptName: '人力资源部 · 招聘组',
    createdAt: '2026-10-26 10:05:00',
    updatedAt: '2026-10-26 10:05:00',
    prompt: PROMPT_TPL('员工手册问答助理', '假期、福利与员工行为规范'),
    skills: skillOf(['s4']),
    mcps: [],
    knowledgeBases: kbOf(['k3']),
    quickQuestions: ['婚假有几天？', '年假可以跨年使用吗？'],
    shareScope: null,
    versionHistory: [
      { version: 'v1.0', action: 'share_submit', actionName: '提交共享', operatorName: '王晓明', remark: '首次申请共享', createdAt: '2026-10-26 10:05:00' },
      { version: 'v1.0', action: 'create', actionName: '创建', operatorName: '王晓明', remark: '手动创建', createdAt: '2026-10-26 09:40:00' }
    ]
  },
  /* 平台预置 */
  ...[
    { id: 2001, name: '智能会议助理', char: '会', color: '#5E9DF5', cat: 1, tags: ['会议', '纪要'], desc: '会议前生成议程，会议中记录要点，会议后输出纪要与待办，并同步到日程。', ver: 'v1.6' },
    { id: 2002, name: 'AI 陪练助理', char: '练', color: '#04D999', cat: 2, tags: ['培训', '陪练'], desc: '按岗位场景模拟客户或员工对话，实时评分并给出改进建议。', ver: 'v2.1' },
    { id: 2003, name: 'AI 面试助理', char: '面', color: '#FF813B', cat: 2, tags: ['面试', '评估'], desc: '按岗位模板发起结构化面试，输出候选人能力画像与面评报告。', ver: 'v1.9' },
    { id: 2004, name: '人效分析助理', char: '效', color: '#3685F2', cat: 2, tags: ['人效', '分析'], desc: '汇总人力投入与产出数据，输出部门人效对比与改善建议。', ver: 'v1.3' },
    { id: 2005, name: '智慧云仓助理', char: '仓', color: '#2468F2', cat: 3, tags: ['仓储', '调度'], desc: '解答库存、盘点与调度规则，支持按库区维度汇总异常。', ver: 'v1.2' },
    { id: 2006, name: '环安合规助理', char: '安', color: '#00B780', cat: 4, tags: ['环安', '合规'], desc: '检索环安法规与内部标准，输出合规检查项与整改建议。', ver: 'v1.1' }
  ].map<AssistantRow>((p) => ({
    assistantId: p.id,
    name: p.name,
    avatarType: 'char',
    avatarChar: p.char,
    avatarUrl: null,
    avatarColor: p.color,
    description: p.desc,
    tags: p.tags,
    categoryId: p.cat,
    source: 'platform',
    shareStatus: 'approved',
    version: p.ver,
    ownerName: null,
    ownerDeptName: null,
    createdAt: '2026-09-01 00:00:00',
    updatedAt: '2026-09-01 00:00:00',
    prompt: `你是九牧集团${p.name}，${p.desc}`,
    skills: [],
    mcps: [],
    knowledgeBases: [],
    quickQuestions: ['你能帮我做什么？', '给我一个使用示例'],
    shareScope: {
      scopeMode: 'PUBLIC',
      orgs: [],
      roles: [],
      positions: [],
      users: [],
      grantTotal: 1860,
      summary: '公开 · 全公司可用'
    },
    versionHistory: []
  }))
]

/** 被授权共享给我的助理（不落 assistant 表，来自 assistant_grant） */
interface GrantRow {
  assistantId: number
  subscribeStatus: 'subscribed' | 'removed'
  grantTime: string
  ownerName: string
  ownerDeptName: string
}

export const grants: GrantRow[] = [
  { assistantId: 3001, subscribeStatus: 'subscribed', grantTime: '2026-10-12 09:00:00', ownerName: '李静', ownerDeptName: '人力资源部 · 招聘组' },
  { assistantId: 3002, subscribeStatus: 'subscribed', grantTime: '2026-10-10 15:20:00', ownerName: '陈志远', ownerDeptName: '智慧云仓事业部 · 仓储运营部' },
  { assistantId: 3003, subscribeStatus: 'subscribed', grantTime: '2026-10-08 10:05:00', ownerName: '赵敏', ownerDeptName: '环安管理部' },
  { assistantId: 3004, subscribeStatus: 'removed', grantTime: '2026-09-28 17:40:00', ownerName: '周涛', ownerDeptName: '经营管理中心 · 报价管理组' }
]

/** 共享助理：配置归创建人，被授权方只读 */
const SHARED_ASSISTANTS: AssistantRow[] = [
  {
    assistantId: 3001, name: '员工关系咨询助理', avatarType: 'char', avatarChar: '员', avatarUrl: null, avatarColor: '#3685F2',
    description: '解答劳动合同、转正、调岗与离职相关问题，输出处理路径与风险提示。',
    tags: ['员工关系', '制度'], categoryId: 2, source: 'custom', shareStatus: 'approved', version: 'v1.1',
    ownerName: '李静', ownerDeptName: '人力资源部 · 招聘组', createdAt: '2026-10-05 09:00:00', updatedAt: '2026-10-11 09:00:00',
    prompt: '你是九牧集团员工关系咨询助理，负责解答劳动合同与用工风险问题。',
    skills: skillOf(['s4']), mcps: mcpOf(['m2']), knowledgeBases: kbOf(['k3']),
    quickQuestions: ['试用期可以延长吗？', '调岗需要员工同意吗？'],
    shareScope: null, versionHistory: []
  },
  {
    assistantId: 3002, name: '仓储盘点助理', avatarType: 'char', avatarChar: '盘', avatarUrl: null, avatarColor: '#2468F2',
    description: '指导盘点作业流程，解释差异处理规则，输出盘点复盘要点。',
    tags: ['盘点', '仓储'], categoryId: 3, source: 'custom', shareStatus: 'approved', version: 'v1.0',
    ownerName: '陈志远', ownerDeptName: '智慧云仓事业部 · 仓储运营部', createdAt: '2026-10-02 15:20:00', updatedAt: '2026-10-02 15:20:00',
    prompt: '你是智慧云仓仓储盘点助理，负责指导盘点作业与差异处理。',
    skills: skillOf(['s5']), mcps: mcpOf(['m5']), knowledgeBases: kbOf(['k4']),
    quickQuestions: ['盘点差异如何处理？'],
    shareScope: null, versionHistory: []
  },
  {
    assistantId: 3003, name: '安全培训助理', avatarType: 'char', avatarChar: '培', avatarUrl: null, avatarColor: '#FF813B',
    description: '按岗位输出安全培训大纲与考试题，支持生成培训签到与考核清单。',
    tags: ['培训', '环安'], categoryId: 4, source: 'custom', shareStatus: 'approved', version: 'v1.3',
    ownerName: '赵敏', ownerDeptName: '环安管理部', createdAt: '2026-09-30 10:05:00', updatedAt: '2026-10-06 10:05:00',
    prompt: '你是环安管理部安全培训助理，负责输出培训大纲与考核题。',
    skills: skillOf(['s8']), mcps: [], knowledgeBases: kbOf(['k5']),
    quickQuestions: ['新员工三级安全教育包括哪些？'],
    shareScope: null, versionHistory: []
  },
  {
    assistantId: 3004, name: '客户报价助理', avatarType: 'char', avatarChar: '报', avatarUrl: null, avatarColor: '#FF4D5D',
    description: '按价格政策校验报价单，解释折扣审批口径，输出报价风险提示。',
    tags: ['报价', '政策'], categoryId: 5, source: 'custom', shareStatus: 'approved', version: 'v1.0',
    ownerName: '周涛', ownerDeptName: '经营管理中心 · 报价管理组', createdAt: '2026-09-20 17:40:00', updatedAt: '2026-09-20 17:40:00',
    prompt: '你是经营管理中心客户报价助理，负责校验报价单与折扣政策。',
    skills: skillOf(['s7']), mcps: [], knowledgeBases: kbOf(['k6']),
    quickQuestions: ['折扣审批权限怎么划分？'],
    shareScope: null, versionHistory: []
  }
]

assistants.push(...SHARED_ASSISTANTS)

/* ============================ 审批种子数据 ============================ */

interface ApprovalRow extends ApprovalDetail {
  requestScope: Scope
}

export const approvals: ApprovalRow[] = [
  {
    approvalId: 9001,
    approvalNo: 'AP20261025001',
    approvalType: 'share',
    status: 'pending',
    assistant: {
      assistantId: 9101,
      name: '车间排班助理',
      avatar: { type: 'char', char: '排', color: '#5E9DF5' },
      description: '按产线节拍与人员技能矩阵生成排班建议，输出缺岗预警。',
      tags: ['排班', '考勤'],
      categoryName: '人资',
      prompt: '你是生产车间排班助理，负责依据节拍与技能矩阵生成排班建议。',
      skills: [{ id: 's4', name: '制度条款检索' }],
      mcps: [{ id: 'm3', name: '考勤打卡服务' }],
      knowledgeBases: [{ id: 'k3', name: '员工考勤制度库' }],
      ownerName: '李静',
      ownerDeptName: '人力资源部 · 招聘组',
      version: 'v1.0'
    },
    submitterName: '李静',
    submitterDept: '人力资源部 · 招聘组',
    submitTime: '2026-10-25 09:12:00',
    scopeAdjusted: false,
    scope: {
      scopeMode: 'RANGE',
      orgs: [{ id: 'O11', name: '人力资源部' }, { id: 'O121', name: '仓储运营部' }],
      roles: [],
      positions: [],
      users: [
        { id: 'u1', name: '李静', deptName: '人力资源部 · 招聘组' },
        { id: 'u2', name: '林晓', deptName: '人力资源部 · 薪酬绩效组' },
        { id: 'u3', name: '陈志远', deptName: '智慧云仓事业部 · 仓储运营部' },
        { id: 'u6', name: '吴磊', deptName: '智慧云仓事业部 · 物流调度部' }
      ],
      grantTotal: 4,
      summary: '人力资源部、仓储运营部 等 4 人'
    },
    requestScope: {
      scopeMode: 'RANGE',
      orgs: [{ id: 'O11', name: '人力资源部' }, { id: 'O121', name: '仓储运营部' }],
      roles: [],
      positions: [],
      users: [
        { id: 'u1', name: '李静', deptName: '人力资源部 · 招聘组' },
        { id: 'u2', name: '林晓', deptName: '人力资源部 · 薪酬绩效组' },
        { id: 'u3', name: '陈志远', deptName: '智慧云仓事业部 · 仓储运营部' },
        { id: 'u6', name: '吴磊', deptName: '智慧云仓事业部 · 物流调度部' }
      ],
      grantTotal: 4,
      summary: '人力资源部、仓储运营部 等 4 人'
    },
    scopeDiff: null
  },
  {
    approvalId: 9002,
    approvalNo: 'AP20261025002',
    approvalType: 'share',
    status: 'pending',
    assistant: {
      assistantId: 9102,
      name: '关务合规问答助理',
      avatar: { type: 'char', char: '关', color: '#3685F2' },
      description: '解答进出口报关资料要求与合规风险点，输出资料清单。',
      tags: ['关务', '合规'],
      categoryName: '智慧云仓',
      prompt: '你是关务合规问答助理，负责解答报关资料与合规风险问题。',
      skills: [{ id: 's4', name: '制度条款检索' }],
      mcps: [{ id: 'm5', name: 'WMS 仓储服务' }],
      knowledgeBases: [{ id: 'k4', name: '仓储作业规范库' }],
      ownerName: '陈志远',
      ownerDeptName: '智慧云仓事业部 · 仓储运营部',
      version: 'v1.0'
    },
    submitterName: '陈志远',
    submitterDept: '智慧云仓事业部 · 仓储运营部',
    submitTime: '2026-10-25 14:36:00',
    scopeAdjusted: false,
    scope: {
      scopeMode: 'RANGE',
      orgs: [{ id: 'O12', name: '智慧云仓事业部' }],
      roles: [],
      positions: [],
      users: [
        { id: 'u3', name: '陈志远', deptName: '智慧云仓事业部 · 仓储运营部' },
        { id: 'u6', name: '吴磊', deptName: '智慧云仓事业部 · 物流调度部' }
      ],
      grantTotal: 2,
      summary: '智慧云仓事业部 等 2 人'
    },
    requestScope: {
      scopeMode: 'RANGE',
      orgs: [{ id: 'O12', name: '智慧云仓事业部' }],
      roles: [],
      positions: [],
      users: [
        { id: 'u3', name: '陈志远', deptName: '智慧云仓事业部 · 仓储运营部' },
        { id: 'u6', name: '吴磊', deptName: '智慧云仓事业部 · 物流调度部' }
      ],
      grantTotal: 2,
      summary: '智慧云仓事业部 等 2 人'
    },
    scopeDiff: null
  }
]

/* ============================ 工具函数 ============================ */

function toCard(row: AssistantRow): AssistantCard {
  const isOwn = row.source === 'custom' || row.source === 'thirdparty'
  const grant = grants.find((g) => g.assistantId === row.assistantId)
  const shared = !!grant
  const actions: AssistantCard['actions'] = []
  if (shared) {
    actions.push('summon')
    actions.push(grant.subscribeStatus === 'subscribed' ? 'remove' : 'resubscribe')
  } else if (row.source === 'platform') {
    actions.push('summon')
    actions.push('shareScope')
  } else if (isOwn) {
    // 需求 F-EXP-004/F-EXP-005：我的助理范围内创建人可编辑、删除；
    // 已共享的额外提供「共享范围」（需求 F-EXP-002）
    actions.push('summon')
    if (row.shareStatus === 'approved') actions.push('shareScope')
    actions.push('edit', 'delete')
  }

  return {
    assistantId: row.assistantId,
    name: row.name,
    avatarType: row.avatarType,
    avatarChar: row.avatarChar,
    avatarUrl: row.avatarUrl,
    avatarColor: row.avatarColor,
    categoryId: row.categoryId,
    categoryName: catName(row.categoryId),
    tags: row.tags,
    description: row.description,
    descriptionTruncated: row.description.length > 60 ? `${row.description.slice(0, 60)}…` : row.description,
    source: shared ? 'shared' : row.source,
    shareStatus: shared ? null : row.shareStatus,
    subscribeStatus: shared ? grant.subscribeStatus : null,
    version: row.version,
    ownerName: shared ? grant.ownerName : row.ownerName,
    ownerTitle: row.ownerDeptName,
    sharedFrom: shared ? { ownerName: grant.ownerName, ownerDeptName: grant.ownerDeptName } : null,
    rejectReason: row.shareStatus === 'rejected' ? '授权范围包含外协单位组织节点，请收敛至本公司部门后重新提交。' : null,
    lastApproverName: row.shareStatus === 'rejected' ? '王建国' : null,
    lastApproveTime: row.shareStatus === 'rejected' ? '2026-10-24 15:02:00' : null,
    authorizedCount: shared ? 0 : row.shareScope?.grantTotal ?? 0,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
    actions
  }
}

function myUserId(): string {
  return (localStorage.getItem('at_role') || 'user') === 'admin' ? '9001' : '1001'
}
function myUserName(): string {
  return (localStorage.getItem('at_role') || 'user') === 'admin' ? '王建国' : '王晓明'
}

/* ============================ 查询接口 ============================ */

export function queryAssistants(params: {
  scope: string
  categoryId?: number
  keyword?: string
  statusFilter?: string
  subscribeFilter?: string
  page: number
  pageSize: number
}): { list: AssistantCard[]; total: number; page: number; pageSize: number } {
  const myName = myUserName()
  let rows: AssistantRow[]

  if (params.scope === 'mine') {
    rows = assistants.filter((e) => (e.source === 'custom' || e.source === 'thirdparty') && e.ownerName === myName && !grants.some((g) => g.assistantId === e.assistantId))
  } else if (params.scope === 'shared') {
    rows = assistants.filter((e) => grants.some((g) => g.assistantId === e.assistantId))
  } else {
    // 需求 F-EXP-002：全部 = 平台预置 ∪ 当前用户自建 ∪ 被授权且已订阅的共享助理
    rows = assistants.filter((e) => {
      if (e.source === 'platform') return true
      const grant = grants.find((g) => g.assistantId === e.assistantId)
      if (grant) return grant.subscribeStatus === 'subscribed'
      return (e.source === 'custom' || e.source === 'thirdparty') && e.ownerName === myName
    })
  }

  let cards = rows.map(toCard)

  if (params.categoryId) {
    cards = cards.filter((c) => c.categoryId === params.categoryId)
  }
  if (params.keyword) {
    const kw = params.keyword.trim().toLowerCase()
    cards = cards.filter(
      (c) => c.name.toLowerCase().includes(kw) || c.tags.some((t) => t.toLowerCase().includes(kw))
    )
  }
  if (params.scope === 'mine' && params.statusFilter) {
    cards = cards.filter((c) => c.shareStatus === params.statusFilter)
  }
  if (params.scope === 'shared' && params.subscribeFilter) {
    cards = cards.filter((c) => c.subscribeStatus === params.subscribeFilter)
  }

  // 排序：platform → mine → shared；组内 createdAt / grantTime 倒序
  const rank = (c: AssistantCard): number => (c.source === 'platform' ? 0 : c.source === 'shared' ? 2 : 1)
  cards.sort((a, b) => rank(a) - rank(b) || b.createdAt.localeCompare(a.createdAt))

  const total = cards.length
  const start = (params.page - 1) * params.pageSize
  return { list: cards.slice(start, start + params.pageSize), total, page: params.page, pageSize: params.pageSize }
}

export function findAssistant(id: number): AssistantRow {
  const row = assistants.find((e) => e.assistantId === id)
  if (!row) throw new ApiError('ASSISTANT_NOT_FOUND', '助理不存在或已删除', null, '')
  return row
}

export function detailOf(id: number): AssistantDetail & { categoryName: string } {
  const row = findAssistant(id)
  const grant = grants.find((g) => g.assistantId === id)
  const readOnly = !!grant
  return {
    ...row,
    categoryName: catName(row.categoryId),
    // 被授权方视角：提示词与能力组成不可见（需求 5.2）
    prompt: readOnly ? null : row.prompt,
    skills: readOnly ? null : row.skills,
    mcps: readOnly ? null : row.mcps,
    knowledgeBases: readOnly ? null : row.knowledgeBases,
    shareScope: readOnly ? null : row.shareScope
  }
}

/* ============================ 写接口 ============================ */

export function createAssistant(payload: AssistantUpsertPayload): AssistantDetail {
  const dup = assistants.find((e) => e.name === payload.name)
  if (dup) throw new ApiError('ASSISTANT_NAME_DUPLICATED', '助理昵称已存在，请修改', { field: 'name' }, '')
  if (!CATEGORIES.some((c) => c.categoryId === payload.categoryId)) {
    throw new ApiError('PARAM_INVALID', '所属分类不存在', { field: 'categoryId' }, '')
  }

  ASSISTANT_SEQ += 1
  const now = nowStr()
  const row: AssistantRow = {
    assistantId: ASSISTANT_SEQ,
    name: payload.name,
    avatarType: payload.avatarType,
    avatarChar: payload.avatarChar,
    avatarUrl: payload.avatarUrl,
    avatarColor: payload.avatarColor,
    description: payload.description,
    tags: payload.tags,
    categoryId: payload.categoryId,
    source: 'custom',
    shareStatus: 'unshared',
    version: 'v1.0',
    ownerName: myUserName(),
    ownerDeptName: '人力资源部 · 招聘组',
    createdAt: now,
    updatedAt: now,
    prompt: payload.prompt,
    skills: skillOf(payload.skillIds),
    mcps: mcpOf(payload.mcpIds),
    knowledgeBases: kbOf(payload.knowledgeBaseIds),
    quickQuestions: payload.quickQuestions,
    shareScope: null,
    versionHistory: [
      { version: 'v1.0', action: 'create', actionName: '创建', operatorName: myUserName(), remark: '手动创建', createdAt: now }
    ]
  }
  assistants.unshift(row)
  return detailOf(row.assistantId)
}

export function updateAssistant(id: number, payload: AssistantUpsertPayload): AssistantDetail {
  const row = findAssistant(id)
  if (row.ownerName !== myUserName()) {
    throw new ApiError('ASSISTANT_NOT_OWNER', '非创建人不可操作', null, '')
  }
  const dup = assistants.find((e) => e.name === payload.name && e.assistantId !== id)
  if (dup) throw new ApiError('ASSISTANT_NAME_DUPLICATED', '助理昵称已存在，请修改', { field: 'name' }, '')

  const minor = Number.parseInt(row.version.replace('v', '').split('.')[1] ?? '0', 10) + 1
  const nextVersion = `v${row.version.replace('v', '').split('.')[0]}.${minor}`

  Object.assign(row, {
    name: payload.name,
    avatarType: payload.avatarType,
    avatarChar: payload.avatarChar,
    avatarUrl: payload.avatarUrl,
    avatarColor: payload.avatarColor,
    description: payload.description,
    tags: payload.tags,
    categoryId: payload.categoryId,
    prompt: payload.prompt,
    skills: skillOf(payload.skillIds),
    mcps: mcpOf(payload.mcpIds),
    knowledgeBases: kbOf(payload.knowledgeBaseIds),
    quickQuestions: payload.quickQuestions,
    version: nextVersion,
    updatedAt: nowStr()
  } satisfies Partial<AssistantRow>)

  row.versionHistory.unshift({
    version: nextVersion,
    action: 'update',
    actionName: '编辑更新',
    operatorName: myUserName(),
    remark: '',
    createdAt: nowStr()
  })
  return detailOf(id)
}

export function deleteImpact(id: number): DeleteImpact {
  const row = findAssistant(id)
  return {
    assistantId: row.assistantId,
    name: row.name,
    authorizedCount: row.shareScope?.grantTotal ?? 0,
    pendingApplyCount: approvals.filter((a) => a.status === 'pending' && a.assistant.assistantId === id).length
  }
}

export function deleteAssistant(id: number): { assistantId: number; deleted: boolean } {
  const row = findAssistant(id)
  if (row.ownerName !== myUserName()) {
    throw new ApiError('ASSISTANT_NOT_OWNER', '非创建人不可删除', null, '')
  }
  const idx = assistants.findIndex((e) => e.assistantId === id)
  assistants.splice(idx, 1)
  approvals.forEach((a) => {
    if (a.assistant.assistantId === id && a.status === 'pending') a.status = 'terminated'
  })
  return { assistantId: id, deleted: true }
}

export function summonAssistant(id: number): SummonResult {
  const row = findAssistant(id)
  const grant = grants.find((g) => g.assistantId === id)
  if (grant && grant.subscribeStatus === 'removed') {
    throw new ApiError('ASSISTANT_NOT_AVAILABLE', '助理已移除，请先重新订阅', null, '')
  }
  return {
    sessionId: `S${Date.now()}`,
    sessionTitle: `召唤 ${row.name}`,
    assistantId: row.assistantId,
    assistantName: row.name,
    AssistantAvatar: {
      type: row.avatarType,
      char: row.avatarChar ?? row.name.slice(0, 1),
      color: row.avatarColor,
      url: row.avatarUrl
    },
    quickQuestions: row.quickQuestions,
    createdAt: nowStr()
  }
}

export function updateSubscription(id: number, action: 'remove' | 'resubscribe'): { assistantId: number; subscribeStatus: string; subscribeTime: string } {
  const grant = grants.find((g) => g.assistantId === id)
  if (!grant) throw new ApiError('GRANT_INVALID', '该助理授权已失效', null, '')
  if (action === 'resubscribe' && grant.subscribeStatus !== 'removed') {
    throw new ApiError('GRANT_INVALID', '该助理授权已失效', null, '')
  }
  grant.subscribeStatus = action === 'remove' ? 'removed' : 'subscribed'
  return { assistantId: id, subscribeStatus: grant.subscribeStatus, subscribeTime: nowStr() }
}

export function submitShare(payload: ShareSubmitPayload): { batchNo: string; approvalIds: number[] } {
  const ids: number[] = []
  payload.assistantIds.forEach((id) => {
    const row = findAssistant(id)
    if (row.shareStatus !== 'unshared' && row.shareStatus !== 'rejected') {
      throw new ApiError('ASSISTANT_STATUS_CHANGED', '所选助理状态已变更，请刷新后重试', { assistantId: id }, '')
    }
  })
  payload.assistantIds.forEach((id) => {
    const row = findAssistant(id)
    row.shareStatus = 'pending'
    const scope = scopeFromPayload(payload.scope)
    const approval: ApprovalRow = {
      approvalId: 9000 + approvals.length + 1,
      approvalNo: `AP${Date.now()}`,
      approvalType: 'share',
      status: 'pending',
      assistant: {
        assistantId: row.assistantId,
        name: row.name,
        avatar: { type: row.avatarType, char: row.avatarChar ?? row.name.slice(0, 1), color: row.avatarColor },
        description: row.description,
        tags: row.tags,
        categoryName: catName(row.categoryId),
        prompt: row.prompt ?? '',
        skills: (row.skills ?? []).map((s) => ({ id: s.id, name: s.name })),
        mcps: (row.mcps ?? []).map((m) => ({ id: m.id, name: m.name })),
        knowledgeBases: (row.knowledgeBases ?? []).map((k) => ({ id: k.id, name: k.name })),
        ownerName: row.ownerName ?? '',
        ownerDeptName: row.ownerDeptName ?? '',
        version: row.version
      },
      submitterName: myUserName(),
      submitterDept: '人力资源部 · 招聘组',
      submitTime: nowStr(),
      scopeAdjusted: false,
      scope,
      requestScope: scope,
      scopeDiff: null
    }
    approvals.push(approval)
    ids.push(approval.approvalId)
    row.versionHistory.unshift({
      version: row.version,
      action: 'share_submit',
      actionName: '提交共享',
      operatorName: myUserName(),
      remark: payload.changeNote ?? '',
      createdAt: nowStr()
    })
  })
  return { batchNo: `B${Date.now()}`, approvalIds: ids }
}

/** 已选范围 → 后端 scope 结构（含展开人数与摘要） */
export function scopeFromPayload(payload: ScopePayload): Scope {
  if (payload.scopeMode === 'PUBLIC') {
    return { scopeMode: 'PUBLIC', orgs: [], roles: [], positions: [], users: [], grantTotal: 1860, summary: '公开 · 全公司可用' }
  }
  // 最终生效颗粒是人：来源维度（组织含下级 / 角色 / 岗位）展开 ∪ 直接添加
  const userIds = new Set<string>(derivedUserIds(payload))
  payload.users.forEach((u) => userIds.add(u))

  const orgs = payload.orgs.map((id) => ({ id, name: orgName(id) }))
  const roles = payload.roles.map((id) => ({ id, name: ROLES.find((r) => r.id === id)?.name ?? id }))
  const positions = payload.positions.map((id) => ({ id, name: POSITIONS.find((p) => p.id === id)?.name ?? id }))
  const users = [...userIds].map((id) => {
    const u = USERS.find((x) => x.id === id)
    return { id, name: u?.name ?? id, deptName: u?.deptName }
  })
  const first = [...orgs, ...positions, ...roles, ...users].slice(0, 2).map((x) => x.name)
  const summary = first.length ? `${first.join('、')} 等 ${users.length} 人` : ''

  return { scopeMode: 'RANGE', orgs, roles, positions, users, grantTotal: users.length, summary }
}

function orgName(id: string): string {
  const walk = (nodes: OrgNode[]): string | null => {
    for (const n of nodes) {
      if (n.id === id) return n.name
      if (n.children) {
        const hit = walk(n.children)
        if (hit) return hit
      }
    }
    return null
  }
  return walk(ORG_TREE) ?? id
}

export function currentGrantUsers(scope: Scope): Array<{ id: string; name: string; deptName?: string; sources: ScopeDim[] }> {
  return scope.users.map((u) => ({ ...u, sources: ['user'] as ScopeDim[] }))
}

/* ============================ 审批接口 ============================ */

export function queryApprovals(params: { approvalType?: string; page: number; pageSize: number }): {
  list: ApprovalCard[]
  total: number
  page: number
  pageSize: number
} {
  let rows = approvals.filter((a) => a.status === 'pending')
  if (params.approvalType) rows = rows.filter((a) => a.approvalType === params.approvalType)
  rows = [...rows].sort((a, b) => a.submitTime.localeCompare(b.submitTime))

  const typeName = (t: string): string => (t === 'share' ? '共享申请' : t === 'scope_change' ? '范围变更' : '下架申请')
  const cards: ApprovalCard[] = rows.map((a) => ({
    approvalId: a.approvalId,
    approvalNo: a.approvalNo,
    approvalType: a.approvalType,
    approvalTypeName: typeName(a.approvalType),
    assistantId: a.assistant.assistantId,
    assistantName: a.assistant.name,
    AssistantAvatar: a.assistant.avatar,
    assistantVersion: a.assistant.version,
    categoryName: a.assistant.categoryName,
    tags: a.assistant.tags,
    submitterName: a.submitterName,
    submitterDept: a.submitterDept,
    submitTime: a.submitTime,
    scopeSummary: a.scope.summary,
    scopeMode: a.scope.scopeMode,
    changeNote: null
  }))

  const total = cards.length
  const start = (params.page - 1) * params.pageSize
  return { list: cards.slice(start, start + params.pageSize), total, page: params.page, pageSize: params.pageSize }
}

export function pendingCount(): number {
  return approvals.filter((a) => a.status === 'pending').length
}

export function findApproval(id: number): ApprovalRow {
  const row = approvals.find((a) => a.approvalId === id)
  if (!row) throw new ApiError('APPROVAL_NOT_FOUND', '审批单不存在', null, '')
  if (row.status !== 'pending') {
    throw new ApiError('APPROVAL_ALREADY_HANDLED', '该申请已被处理', null, '')
  }
  return row
}

export function adjustApprovalScope(id: number, scope: Scope): { scope: Scope; scopeDiff: ApprovalDetail['scopeDiff'] } {
  const row = findApproval(id)
  row.scope = scope
  row.scopeAdjusted = true
  const before = new Set(row.requestScope.users.map((u) => u.id))
  const after = new Set(scope.users.map((u) => u.id))
  const added = scope.users.filter((u) => !before.has(u.id)).map((u) => ({ dim: 'user', id: u.id, name: u.name }))
  const removed = row.requestScope.users.filter((u) => !after.has(u.id)).map((u) => ({ dim: 'user', id: u.id, name: u.name }))
  row.scopeDiff = { addedCount: added.length, removedCount: removed.length, added, removed }
  return { scope: row.scope, scopeDiff: row.scopeDiff }
}

export function approve(id: number): ApprovalDecisionResult {
  const row = findApproval(id)
  row.status = 'approved'
  return {
    approvalId: row.approvalId,
    status: 'approved',
    assistantId: row.assistant.assistantId,
    shareStatus: 'approved',
    grantTotal: row.scope.grantTotal,
    approveTime: nowStr()
  }
}

export function reject(id: number, reason: string): ApprovalDecisionResult {
  const row = findApproval(id)
  row.status = 'rejected'
  return {
    approvalId: row.approvalId,
    status: 'rejected',
    assistantId: row.assistant.assistantId,
    shareStatus: 'rejected',
    rejectReason: reason,
    approveTime: nowStr()
  }
}

/* ============================ 分类 ============================ */

export function addCategory(name: string): CategoryItem {
  if (name.length > 10) throw new ApiError('CATEGORY_NAME_TOO_LONG', '分类名称不超过 10 个字符', { field: 'name' }, '')
  if (CATEGORIES.some((c) => c.name === name)) {
    throw new ApiError('CATEGORY_DUPLICATED', '分类名称已存在', { field: 'name' }, '')
  }
  const item: CategoryItem = {
    categoryId: Math.max(...CATEGORIES.map((c) => c.categoryId)) + 1,
    name,
    isBuiltin: false,
    sortNo: (CATEGORIES.length + 1) * 10
  }
  CATEGORIES.push(item)
  return item
}

export function currentUserId(): string {
  return myUserId()
}
