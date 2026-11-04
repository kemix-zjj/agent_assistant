/* ============================================================
 * 数智助理 · 助理团 — 原型运行时
 * 职责：Mock 数据 / 左侧菜单 / 页面路由 / 缩放 / 通用组件
 * 设计规范：JMBOS UIUE（顶导 42px · 侧边 180px · 正文 13px · 间距 8px · 圆角 4px）
 * ============================================================ */
(function () {
  'use strict';

  /* ============================================================
   * 一、Mock 数据（纯前端，无后端依赖）
   * ============================================================ */
  var CATEGORIES = ['协同办公', '人资', '智慧云仓', '环安', '经营管理'];

  var ORG_TREE = [{
    id: 'O1', name: '九牧集团有限公司', children: [
      {
        id: 'O11', name: '人力资源部', children: [
          { id: 'O111', name: '招聘组' },
          { id: 'O112', name: '薪酬绩效组' }
        ]
      },
      {
        id: 'O12', name: '智慧云仓事业部', children: [
          { id: 'O121', name: '仓储运营部' },
          { id: 'O122', name: '物流调度部' }
        ]
      },
      { id: 'O13', name: '环安管理部' },
      { id: 'O14', name: '经营管理中心', children: [{ id: 'O141', name: '报价管理组' }] }
    ]
  }];

  /* 人员是最小授权颗粒：组织 / 岗位 / 角色 仅用于批量展开人员 */
  var USERS = [
    { id: 'u1', name: '李静', dept: '人力资源部 · 招聘组', orgId: 'O111', positionId: 'p1', roles: ['r3', 'r4', 'r8'] },
    { id: 'u2', name: '陈志远', dept: '智慧云仓事业部 · 仓储运营部', orgId: 'O121', positionId: 'p3', roles: ['r2', 'r8'] },
    { id: 'u3', name: '赵敏', dept: '环安管理部', orgId: 'O13', positionId: 'p5', roles: ['r7', 'r8'] },
    { id: 'u4', name: '周涛', dept: '经营管理中心 · 报价管理组', orgId: 'O141', positionId: 'p6', roles: ['r2', 'r8'] },
    { id: 'u5', name: '林晓', dept: '人力资源部 · 薪酬绩效组', orgId: 'O112', positionId: 'p2', roles: ['r5', 'r8'] },
    { id: 'u6', name: '吴磊', dept: '智慧云仓事业部 · 物流调度部', orgId: 'O122', positionId: 'p4', roles: ['r8'] }
  ];

  /* 授权维度：岗位 / 角色（组织、人员复用 ORG_TREE、USERS） */
  var ROLES = [
    { id: 'r1', name: '公司管理员', desc: '具备助理审批与全局授权权限' },
    { id: 'r2', name: '部门负责人', desc: '查看本部门数据与审批结果' },
    { id: 'r3', name: 'HRBP', desc: '负责业务单元人力事务' },
    { id: 'r4', name: '招聘专员', desc: '负责简历筛选与面试安排' },
    { id: 'r5', name: '薪酬专员', desc: '负责薪资核算与个税申报' },
    { id: 'r6', name: '车间主管', desc: '负责产线排班与现场管理' },
    { id: 'r7', name: '安全员', desc: '负责环安巡检与隐患整改' },
    { id: 'r8', name: '普通员工', desc: '仅可查看与本人相关内容' }
  ];

  var POSITIONS = [
    { id: 'p1', name: '招聘专员', dept: '人力资源部 · 招聘组' },
    { id: 'p2', name: '薪酬绩效专员', dept: '人力资源部 · 薪酬绩效组' },
    { id: 'p3', name: '仓储管理员', dept: '智慧云仓事业部 · 仓储运营部' },
    { id: 'p4', name: '物流调度员', dept: '智慧云仓事业部 · 物流调度部' },
    { id: 'p5', name: '环安工程师', dept: '环安管理部' },
    { id: 'p6', name: '报价专员', dept: '经营管理中心 · 报价管理组' },
    { id: 'p7', name: '车间班组长', dept: '制造中心 · 一车间' },
    { id: 'p8', name: '质检员', dept: '制造中心 · 质检部' }
  ];

  /* 内部市场：集团自研沉淀；外部市场：生态市场上架 */
  var SKILL_CATALOG = [
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
  ];

  var MCP_CATALOG = [
    { id: 'm1', name: '企业微信通讯录', type: '组织数据', market: 'internal' },
    { id: 'm2', name: 'HR 主数据服务', type: '业务系统', market: 'internal' },
    { id: 'm3', name: '考勤打卡服务', type: '业务系统', market: 'internal' },
    { id: 'm4', name: '薪酬核算服务', type: '业务系统', market: 'internal' },
    { id: 'm5', name: 'WMS 仓储服务', type: '业务系统', market: 'external' },
    { id: 'm6', name: '隐患台账服务', type: '业务系统', market: 'external' },
    { id: 'm7', name: '飞书多维表格', type: '第三方应用', market: 'external' },
    { id: 'm8', name: '钉钉待办', type: '第三方应用', market: 'external' }
  ];

  var KB_CATALOG = [
    { id: 'k1', name: '招聘管理制度库', count: 128, market: 'internal',
      files: ['招聘管理办法.pdf', '面试评估操作指引.docx', '校园招聘流程.pdf'] },
    { id: 'k2', name: '薪酬福利政策库', count: 96, market: 'internal',
      files: ['薪酬结构管理办法.pdf', '个税专项附加扣除指引.pdf', '社保公积金缴纳标准.xlsx'] },
    { id: 'k3', name: '员工考勤制度库', count: 64, market: 'internal',
      files: ['考勤管理制度.pdf', '请假与调休细则.docx', '加班管理规定.pdf'] },
    { id: 'k4', name: '仓储作业规范库', count: 212, market: 'internal',
      files: ['仓储盘点作业指导书.pdf', '库区安全管理规范.pdf', '出入库操作手册.docx'] },
    { id: 'k5', name: '环安法规与标准库', count: 158, market: 'internal',
      files: ['安全生产法（2021）.pdf', '隐患排查治理标准.docx', '环保合规清单.xlsx'] },
    { id: 'k6', name: '报价政策库', count: 43, market: 'internal',
      files: ['价格政策管理办法.pdf', '折扣审批权限表.xlsx'] }
  ];

  var PROMPT_TPL = '你是九牧集团人力资源部的{0}，负责回答员工关于{1}的问题。\n' +
    '回答要求：先给结论，再给制度依据，涉及个人数据时须提示员工自行核对；\n' +
    '无法确认的问题必须说明"需人工确认"，不得编造条款编号。';

  var ASSISTANTS = [
    /* ---- 自建助理（我的助理）---- */
    {
      id: 'E1001', name: '招聘面试助理', avatar: '招', color: '#3685F2', source: 'custom', category: '人资',
      tags: ['招聘', '面试', '校招'], owner: '王晓明', ownerDept: '人力资源部 · 招聘组',
      desc: '面向候选人与面试官的双向问答助理，可生成面试提纲、评估维度与面评意见，并解释招聘制度条款。',
      prompt: PROMPT_TPL.replace('{0}', '招聘面试助理').replace('{1}', '招聘流程、面试评估与录用规则'),
      skills: ['s1', 's2', 's4'], mcps: ['m1', 'm2'], kbs: ['k1'],
      status: 'approved', authorizedCount: 2, createTime: '2026-10-18 09:24', updateTime: '2026-10-23 16:40',
      version: 'v1.2', scope: { orgs: ['O11'], users: ['u5'] },
      quickQuestions: ['校招面试提问清单怎么设计？', '如何评估候选人的稳定性？', '录用审批需要准备哪些材料？'],
      history: [
        { version: 'v1.2', action: '编辑更新', operator: '王晓明', time: '2026-10-23 16:40', remark: '补充校招场景提示词' },
        { version: 'v1.1', action: '授权范围变更', operator: '王建国', time: '2026-10-21 10:12', remark: '新增薪酬绩效组（林晓）' },
        { version: 'v1.0', action: '创建', operator: '王晓明', time: '2026-10-18 09:24', remark: '手动创建' }
      ]
    },
    {
      id: 'E1002', name: '薪酬核算助理', avatar: '薪', color: '#04D999', source: 'custom', category: '人资',
      tags: ['薪酬', '核算'], owner: '王晓明', ownerDept: '人力资源部 · 招聘组',
      desc: '按月解释薪资结构与个税口径，核对薪资异常项并给出调整建议，支持按部门维度汇总。',
      prompt: PROMPT_TPL.replace('{0}', '薪酬核算助理').replace('{1}', '薪资结构、个税与社保公积金口径'),
      skills: ['s3', 's4'], mcps: ['m2', 'm4'], kbs: ['k2'],
      status: 'approved', authorizedCount: 6, createTime: '2026-10-15 14:02', updateTime: '2026-10-22 10:08',
      version: 'v1.0', scope: { orgs: ['O1'], users: [] },
      quickQuestions: ['本月薪资异常项怎么核对？', '个税专项附加扣除怎么处理？'],
      history: [
        { version: 'v1.0', action: '创建并共享', operator: '王晓明', time: '2026-10-15 14:02', remark: '手动创建，首次申请共享' }
      ]
    },
    {
      id: 'E1003', name: '考勤答疑助理', avatar: '勤', color: '#FF813B', source: 'custom', category: '人资',
      tags: ['考勤', '制度'], owner: '王晓明', ownerDept: '人力资源部 · 招聘组',
      desc: '解答请假、调休、加班与补卡规则，可按制度条款给出依据，并提示需要走流程的场景。',
      prompt: PROMPT_TPL.replace('{0}', '考勤答疑助理').replace('{1}', '请假、调休、加班与补卡规则'),
      skills: ['s4'], mcps: ['m3'], kbs: ['k3'],
      status: 'unshared', authorizedCount: 0, createTime: '2026-10-21 11:16', updateTime: '2026-10-21 11:16',
      version: 'v1.0', scope: { orgs: [], users: [] },
      history: [
        { version: 'v1.0', action: '创建', operator: '王晓明', time: '2026-10-21 11:16', remark: '手动创建' }
      ]
    },
    {
      id: 'E1004', name: '环安巡检助理', avatar: '环', color: '#FF4D5D', source: 'custom', category: '环安',
      tags: ['环安', '巡检', '隐患'], owner: '王晓明', ownerDept: '人力资源部 · 招聘组',
      desc: '输出车间巡检清单与隐患整改建议，可按厂区维度汇总隐患分布与整改完成率。',
      prompt: PROMPT_TPL.replace('{0}', '环安巡检助理').replace('{1}', '车间巡检标准与隐患整改要求'),
      skills: ['s5'], mcps: ['m6'], kbs: ['k5'],
      status: 'rejected', authorizedCount: 0, createTime: '2026-10-19 16:30', updateTime: '2026-10-24 15:02',
      rejectReason: '授权范围包含外协单位组织节点，请收敛至本公司部门后重新提交。',
      approver: '王建国', approveTime: '2026-10-24 15:02', lastScope: { orgs: ['O1'], users: ['u2'] },
      version: 'v1.1', scope: { orgs: ['O1'], users: ['u2'] },
      history: [
        { version: 'v1.1', action: '编辑更新', operator: '王晓明', time: '2026-10-24 14:20', remark: '补充隐患分级说明' },
        { version: 'v1.0', action: '创建并共享', operator: '王晓明', time: '2026-10-19 16:30', remark: '手动创建，首次申请共享' }
      ]
    },
    /* ---- 平台预置助理 ---- */
    { id: 'P01', name: '智能会议助理', avatar: '会', color: '#5E9DF5', source: 'platform', category: '协同办公', tags: ['会议', '纪要'], desc: '会议前生成议程，会议中记录要点，会议后输出纪要与待办，并同步到日程。', status: 'platform', version: 'v1.6' },
    { id: 'P02', name: 'AI 陪练助理', avatar: '练', color: '#04D999', source: 'platform', category: '人资', tags: ['培训', '陪练'], desc: '按岗位场景模拟客户或员工对话，实时评分并给出改进建议。', status: 'platform', version: 'v2.1' },
    { id: 'P03', name: 'AI 面试助理', avatar: '面', color: '#FF813B', source: 'platform', category: '人资', tags: ['面试', '评估'], desc: '按岗位模板发起结构化面试，输出候选人能力画像与面评报告。', status: 'platform', version: 'v1.9' },
    { id: 'P04', name: '人效分析助理', avatar: '效', color: '#3685F2', source: 'platform', category: '人资', tags: ['人效', '分析'], desc: '汇总人力投入与产出数据，输出部门人效对比与改善建议。', status: 'platform', version: 'v1.3' },
    { id: 'P05', name: '智慧云仓助理', avatar: '仓', color: '#2468F2', source: 'platform', category: '智慧云仓', tags: ['仓储', '调度'], desc: '解答库存、盘点与调度规则，支持按库区维度汇总异常。', status: 'platform', version: 'v1.2' },
    { id: 'P06', name: '环安合规助理', avatar: '安', color: '#00B780', source: 'platform', category: '环安', tags: ['环安', '合规'], desc: '检索环安法规与内部标准，输出合规检查项与整改建议。', status: 'platform', version: 'v1.1' },
    /* ---- 被授权共享助理 ---- */
    {
      id: 'S2001', name: '员工关系咨询助理', avatar: '员', color: '#3685F2', source: 'shared', category: '人资',
      tags: ['员工关系', '制度'], owner: '李静', ownerDept: '人力资源部 · 招聘组',
      desc: '解答劳动合同、转正、调岗与离职相关问题，输出处理路径与风险提示。',
      prompt: '你是九牧集团员工关系咨询助理，负责解答劳动合同与用工风险问题。',
      skills: ['s4'], mcps: ['m2'], kbs: ['k3'],
      subscribed: true, authorizedAt: '2026-10-12 09:00', version: 'v1.1'
    },
    {
      id: 'S2002', name: '仓储盘点助理', avatar: '盘', color: '#2468F2', source: 'shared', category: '智慧云仓',
      tags: ['盘点', '仓储'], owner: '陈志远', ownerDept: '智慧云仓事业部 · 仓储运营部',
      desc: '指导盘点作业流程，解释差异处理规则，输出盘点复盘要点。',
      prompt: '你是智慧云仓仓储盘点助理，负责指导盘点作业与差异处理。',
      skills: ['s5'], mcps: ['m5'], kbs: ['k4'],
      subscribed: true, authorizedAt: '2026-10-10 15:20', version: 'v1.0'
    },
    {
      id: 'S2003', name: '安全培训助理', avatar: '培', color: '#FF813B', source: 'shared', category: '环安',
      tags: ['培训', '环安'], owner: '赵敏', ownerDept: '环安管理部',
      desc: '按岗位输出安全培训大纲与考试题，支持生成培训签到与考核清单。',
      prompt: '你是环安管理部安全培训助理，负责输出培训大纲与考核题。',
      skills: ['s8'], mcps: [], kbs: ['k5'],
      subscribed: true, authorizedAt: '2026-10-08 10:05', version: 'v1.3'
    },
    {
      id: 'S2004', name: '客户报价助理', avatar: '报', color: '#FF4D5D', source: 'shared', category: '经营管理',
      tags: ['报价', '政策'], owner: '周涛', ownerDept: '经营管理中心 · 报价管理组',
      desc: '按价格政策校验报价单，解释折扣审批口径，输出报价风险提示。',
      prompt: '你是经营管理中心客户报价助理，负责校验报价单与折扣政策。',
      skills: ['s7'], mcps: [], kbs: ['k6'],
      subscribed: false, authorizedAt: '2026-09-28 17:40', version: 'v1.0'
    }
  ];

  /* 审批单类型：share 共享申请 / offline 下架申请 / scope 授权范围变更 */
  var APPROVALS = [
    {
      id: 'AP20261025001', type: 'share', assistantId: 'X9001', assistantName: '车间排班助理', avatar: '排', color: '#5E9DF5',
      category: '人资', tags: ['排班', '考勤'], desc: '按产线节拍与人员技能矩阵生成排班建议，输出缺岗预警。',
      prompt: '你是生产车间排班助理，负责依据节拍与技能矩阵生成排班建议。',
      skills: ['s4'], mcps: ['m3'], kbs: ['k3'], version: 'v1.0',
      owner: '李静', ownerDept: '人力资源部 · 招聘组',
      submitter: '李静', submitterDept: '人力资源部 · 招聘组', submitTime: '2026-10-25 09:12',
      changeNote: '首次申请共享，覆盖招聘组与仓储运营部',
      scope: { orgs: ['O11', 'O121'], users: ['u6'] }, status: 'pending'
    },
    {
      id: 'AP20261025002', type: 'share', assistantId: 'X9002', assistantName: '关务合规问答助理', avatar: '关', color: '#3685F2',
      category: '智慧云仓', tags: ['关务', '合规'], desc: '解答进出口报关资料要求与合规风险点，输出资料清单。',
      prompt: '你是关务合规问答助理，负责解答报关资料与合规风险问题。',
      skills: ['s4'], mcps: ['m5'], kbs: ['k4'], version: 'v1.0',
      owner: '陈志远', ownerDept: '智慧云仓事业部 · 仓储运营部',
      submitter: '陈志远', submitterDept: '智慧云仓事业部 · 仓储运营部', submitTime: '2026-10-25 14:36',
      changeNote: '首次申请共享，仅限智慧云仓事业部',
      scope: { orgs: ['O12'], users: [] }, status: 'pending'
    }
  ];

  /* ============================================================
   * 二、全局状态
   * ============================================================ */
  var ROLE_USERS = {
    user: { name: '王晓明', title: '普通员工', dept: '人力资源部 · 招聘组', avatar: '王' },
    admin: { name: '王建国', title: '公司管理员', dept: '人力资源部', avatar: '管' }
  };

  var STORE = {
    role: localStorage.getItem('at_role') || 'user',
    assistants: ASSISTANTS,
    approvals: APPROVALS,
    categories: CATEGORIES,
    orgTree: ORG_TREE,
    users: USERS,
    roles: ROLES,
    positions: POSITIONS,
    skills: SKILL_CATALOG,
    mcps: MCP_CATALOG,
    kbs: KB_CATALOG,
    session: null
  };
  window.__store = STORE;
  window.__roleUser = function () { return ROLE_USERS[STORE.role] || ROLE_USERS.user; };
  window.__isAdmin = function () { return STORE.role === 'admin'; };

  /* ============================================================
   * 三、通用工具
   * ============================================================ */
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  window.esc = esc;

  window.Icon = function (id, cls) {
    return '<svg class="icon ' + (cls || '') + '"><use href="#' + id + '"></use></svg>';
  };

  window.Tag = function (type, text) {
    return '<span class="tag tag-' + (type || 'default') + '">' + esc(text) + '</span>';
  };

  window.Pager = function (total, cur, size) {
    size = size || 10;
    var pages = Math.max(1, Math.ceil(total / size));
    cur = cur || 1;
    var btns = '<button class="page-btn" disabled>' + window.Icon('icon-chevron-left') + '</button>';
    for (var i = 1; i <= pages; i++) {
      btns += '<button class="page-btn' + (i === cur ? ' active' : '') + '">' + i + '</button>';
    }
    btns += '<button class="page-btn" disabled>' + window.Icon('icon-chevron-right') + '</button>';
    return '<div class="pagination-wrapper"><div class="pagination-info">共 <span class="count">' + total +
      '</span> 条 · 每页 <select class="page-size-select"><option>10</option><option>20</option><option>50</option></select></div>' +
      '<div class="pagination">' + btns + '<span class="page-jump">跳至 <input class="page-jump-input" value="' + cur + '"> 页</span></div></div>';
  };

  window.findOrg = function (id) {
    var hit = null;
    (function walk(list) {
      list.forEach(function (n) {
        if (n.id === id) hit = n;
        if (n.children) walk(n.children);
      });
    })(STORE.orgTree);
    return hit;
  };
  window.findUser = function (id) {
    return STORE.users.filter(function (u) { return u.id === id; })[0] || null;
  };
  window.findRole = function (id) {
    return STORE.roles.filter(function (r) { return r.id === id; })[0] || null;
  };
  window.findPosition = function (id) {
    return STORE.positions.filter(function (p) { return p.id === id; })[0] || null;
  };

  /* ============================================================
   * 授权范围（按组织 / 岗位 / 角色 / 人员）— 穿梭框
   * 规范：JMBOS UIUE · 边框 #D2D7E1 · 圆角 4px · 正文 13px
   * 面板头 36px(#F4F7F9) · 行高 32px · 复选框 14px
   * ============================================================ */
  var SCOPE_DIMS = [
    { key: 'orgs', label: '按组织' },
    { key: 'positions', label: '按岗位' },
    { key: 'roles', label: '按角色' },
    { key: 'users', label: '按人员' }
  ];

  function flattenOrgs(nodes, level, out) {
    (nodes || []).forEach(function (n) {
      out.push({ id: n.id, name: n.name, meta: level === 0 ? '组织' : '', level: level });
      if (n.children) flattenOrgs(n.children, level + 1, out);
    });
    return out;
  }

  window.scopeItems = function (key) {
    if (key === 'orgs') return flattenOrgs(STORE.orgTree, 0, []);
    if (key === 'roles') {
      return STORE.roles.map(function (r) { return { id: r.id, name: r.name, meta: r.desc }; });
    }
    if (key === 'positions') {
      return STORE.positions.map(function (p) { return { id: p.id, name: p.name, meta: p.dept }; });
    }
    return STORE.users.map(function (u) { return { id: u.id, name: u.name, meta: u.dept }; });
  };

  /* 组织节点自身 + 全部下级节点 id */
  window.orgIdsUnder = function (orgId) {
    var out = [];
    (function walk(list) {
      (list || []).forEach(function (n) {
        if (n.id === orgId) {
          (function collect(node) {
            out.push(node.id);
            (node.children || []).forEach(collect);
          })(n);
        } else if (n.children) {
          walk(n.children);
        }
      });
    })(STORE.orgTree);
    return out;
  };

  /* 授权范围 → 生效人员（人是最小颗粒）
   * scope = { orgs, roles, positions, users(单独添加), excluded(显式移除) }
   * 生效人员 = 组织(含下级) ∪ 角色 ∪ 岗位 ∪ 单独添加 − 显式移除 */
  window.scopePeople = function (scope) {
    scope = scope || {};
    var picked = {};

    /* 公开授权：全公司可用 */
    if (scope.public) {
      STORE.users.forEach(function (u) { picked[u.id] = true; });
      return Object.keys(picked);
    }

    (scope.orgs || []).forEach(function (oid) {
      var sub = window.orgIdsUnder(oid);
      STORE.users.forEach(function (u) { if (sub.indexOf(u.orgId) >= 0) picked[u.id] = true; });
    });
    (scope.positions || []).forEach(function (pid) {
      STORE.users.forEach(function (u) { if (u.positionId === pid) picked[u.id] = true; });
    });
    (scope.roles || []).forEach(function (rid) {
      STORE.users.forEach(function (u) { if ((u.roles || []).indexOf(rid) >= 0) picked[u.id] = true; });
    });
    (scope.users || []).forEach(function (uid) { picked[uid] = true; });
    (scope.excluded || []).forEach(function (uid) { delete picked[uid]; });

    return Object.keys(picked);
  };

  /* 授权对象数量 = 生效人员数 */
  window.scopeCount = function (scope) {
    return window.scopePeople(scope).length;
  };

  /* 只读展示：人员 6（组织 1 · 岗位 1） */
  window.scopeSummary = function (scope) {
    scope = scope || {};
    var n = window.scopeCount(scope);
    if (!n) return '未设置';
    var src = [];
    if (scope.public) src.push('公开');
    if ((scope.orgs || []).length) src.push('组织 ' + scope.orgs.length);
    if ((scope.positions || []).length) src.push('岗位 ' + scope.positions.length);
    if ((scope.roles || []).length) src.push('角色 ' + scope.roles.length);
    if ((scope.users || []).length) src.push('单独添加 ' + scope.users.length);
    return '人员 ' + n + (src.length ? '（' + src.join(' · ') + '）' : '');
  };

  /* 只读展示：授权来源 chips + 生效人员 chips */
  window.scopeChipsHtml = function (scope) {
    scope = scope || {};
    var html = '';
    if (scope.public) {
      html += '<span class="scope-chip scope-chip-src">公开 · 全公司可用</span>';
    }
    (scope.orgs || []).forEach(function (id) {
      var n = window.findOrg(id);
      html += '<span class="scope-chip scope-chip-src">组织 · ' + esc(n ? n.name : id) + '</span>';
    });
    (scope.positions || []).forEach(function (id) {
      var p = window.findPosition(id);
      html += '<span class="scope-chip scope-chip-src">岗位 · ' + esc(p ? p.name : id) + '</span>';
    });
    (scope.roles || []).forEach(function (id) {
      var r = window.findRole(id);
      html += '<span class="scope-chip scope-chip-src">角色 · ' + esc(r ? r.name : id) + '</span>';
    });
    window.scopePeople(scope).forEach(function (id) {
      var u = window.findUser(id);
      html += '<span class="scope-chip">' + esc(u ? u.name : id) +
        (u ? '<span class="scope-chip-meta">' + esc(u.dept) + '</span>' : '') + '</span>';
    });
    return html;
  };

  /* 穿梭框组件：先插入 html，再 mount(root) 绑定交互，返回 { get(), people() }
   * 交互：按页签切换维度，每个页签都是「左侧未选择 / 右侧已选择 + 中间转移按钮」
   * 语义：组织 / 岗位 / 角色 只是批量选择方式，最终授权颗粒是人；
   *       切换「按人员」时，已选组织/岗位/角色下的人员会自动出现在右侧，可继续增删。
   * opts.dims   仅展示指定维度，如 ['orgs', 'users']，默认四类全展示
   * opts.limits 各维度选择上限，如 { orgs: 50, users: 200 }，默认不限
   */
  window.ScopeTransfer = function (opts) {
    opts = opts || {};
    var scope = opts.scope || {};
    var uid = opts.prefix || ('tf' + Math.floor(Math.random() * 100000));
    var keyword = '';

    var dims = opts.dims && opts.dims.length
      ? SCOPE_DIMS.filter(function (d) { return opts.dims.indexOf(d.key) >= 0; })
      : SCOPE_DIMS;
    if (!dims.length) dims = SCOPE_DIMS;
    var limits = opts.limits || {};
    var activeDim = dims[0].key;

    function labelOf(key) {
      var hit = dims.filter(function (d) { return d.key === key; })[0];
      return hit ? hit.label : key;
    }

    /* 三个来源维度的选择态 */
    var srcSel = { orgs: {}, roles: {}, positions: {} };
    dims.forEach(function (d) {
      if (d.key === 'users') return;
      (scope[d.key] || []).forEach(function (id) { srcSel[d.key][id] = true; });
    });
    /* 单独添加的人员 / 从来源带入后被显式移除的人员 */
    var manual = {};
    (scope.users || []).forEach(function (id) { manual[id] = true; });
    var excluded = {};
    (scope.excluded || []).forEach(function (id) { excluded[id] = true; });

    var html =
      '<div class="tf" id="' + uid + '">' +
        '<div class="tf-tabs" data-tabs></div>' +
        '<div class="tf-hint" data-hint></div>' +
        '<div class="tf-body">' +
          '<div class="tf-panel">' +
            '<div class="tf-panel-head">' +
              '<label class="checkbox-item"><input type="checkbox" data-all><span>全选</span></label>' +
              '<span>可选 <b class="tf-num" data-total>0</b> 项</span>' +
            '</div>' +
            '<div class="tf-search"><input data-search placeholder="搜索名称 / 部门"></div>' +
            '<div class="tf-list" data-left></div>' +
          '</div>' +
          '<div class="tf-ops">' +
            '<button type="button" class="tf-btn tf-btn-primary" data-move="toRight" title="移入已选">›</button>' +
            '<button type="button" class="tf-btn tf-btn-primary" data-move="allRight" title="全部移入">»</button>' +
            '<button type="button" class="tf-btn" data-move="toLeft" title="移出已选">‹</button>' +
            '<button type="button" class="tf-btn" data-move="allLeft" title="全部移出">«</button>' +
          '</div>' +
          '<div class="tf-panel">' +
            '<div class="tf-panel-head">' +
              '<span>已选 <b class="tf-num" data-selcount>0</b> 项</span>' +
              '<span class="tf-clear" data-clear>清空</span>' +
            '</div>' +
            '<div class="tf-search tf-search-hidden"></div>' +
            '<div class="tf-list" data-right></div>' +
          '</div>' +
        '</div>' +
        '<div class="tf-summary" data-summary></div>' +
      '</div>';

    function mount(root) {
      var box = root.querySelector('#' + uid) || root;

      function idsOf(map) {
        return Object.keys(map || {}).filter(function (k) { return map[k]; });
      }

      /* 来源维度（组织含下级 / 岗位 / 角色）展开出的人员 */
      function derivedMap() {
        var out = {};
        idsOf(srcSel.orgs).forEach(function (oid) {
          var sub = window.orgIdsUnder(oid);
          STORE.users.forEach(function (u) { if (sub.indexOf(u.orgId) >= 0) out[u.id] = true; });
        });
        idsOf(srcSel.positions).forEach(function (pid) {
          STORE.users.forEach(function (u) { if (u.positionId === pid) out[u.id] = true; });
        });
        idsOf(srcSel.roles).forEach(function (rid) {
          STORE.users.forEach(function (u) { if ((u.roles || []).indexOf(rid) >= 0) out[u.id] = true; });
        });
        return out;
      }

      /* 单独添加（不来自任何来源维度）的人员 */
      function manualOnlyMap() {
        var d = derivedMap();
        var out = {};
        idsOf(manual).forEach(function (id) { if (!d[id]) out[id] = true; });
        return out;
      }

      /* 生效授权人员 = 来源展开 ∪ 单独添加 − 显式移除 */
      function effectiveMap() {
        var d = derivedMap();
        var out = {};
        Object.keys(d).forEach(function (id) { if (!excluded[id]) out[id] = true; });
        idsOf(manualOnlyMap()).forEach(function (id) { if (!excluded[id]) out[id] = true; });
        return out;
      }

      /* 当前页签下“已选”的映射 */
      function selectedOf(key) {
        if (key === 'users') return effectiveMap();
        return srcSel[key] || {};
      }

      function countOf(key) {
        return idsOf(selectedOf(key)).length;
      }

      /* 来源变化后，清理已无来源的“显式移除”记录 */
      function pruneExcluded() {
        var d = derivedMap();
        Object.keys(excluded).forEach(function (id) { if (!d[id]) delete excluded[id]; });
      }

      /* 该人员的授权来源标签：组织 / 岗位 / 角色 / 直接添加 */
      function sourceTagsOf(userId) {
        var u = window.findUser(userId);
        if (!u) return [];
        var tags = [];
        if (idsOf(srcSel.orgs).some(function (oid) { return window.orgIdsUnder(oid).indexOf(u.orgId) >= 0; })) tags.push('组织');
        if (idsOf(srcSel.positions).some(function (pid) { return u.positionId === pid; })) tags.push('岗位');
        if (idsOf(srcSel.roles).some(function (rid) { return (u.roles || []).indexOf(rid) >= 0; })) tags.push('角色');
        if (manualOnlyMap()[userId]) tags.push('直接添加');
        return tags;
      }

      function renderTabs() {
        box.querySelector('[data-tabs]').innerHTML = dims.map(function (d) {
          var n = countOf(d.key);
          var max = limits[d.key];
          return '<div class="tf-tab' + (d.key === activeDim ? ' active' : '') + '" data-dim="' + d.key + '">' +
            d.label + '<span class="tf-tab-count' + (n ? ' has' : '') + '">' +
            (max ? n + '/' + max : n) + '</span></div>';
        }).join('');
        box.querySelectorAll('[data-dim]').forEach(function (el) {
          el.addEventListener('click', function () {
            activeDim = el.getAttribute('data-dim');
            keyword = '';
            box.querySelector('[data-search]').value = '';
            renderAll();
          });
        });
      }

      function renderHint() {
        box.querySelector('[data-hint]').innerHTML = activeDim === 'users'
          ? '右侧为最终生效的授权人员；在此移出的人员，即使所属组织/岗位/角色仍在授权范围内，也不再对其生效。'
          : '在左侧勾选后点击 › 移入右侧；所选' + labelOf(activeDim).replace('按', '') + '下的人员会自动带入「按人员」，可在人员页签继续增删。';
      }

      function renderLists() {
        var all = window.scopeItems(activeDim);
        var sel = selectedOf(activeDim);
        var kw = keyword.trim().toLowerCase();

        var leftItems = all.filter(function (it) { return !sel[it.id]; });
        if (kw) {
          leftItems = leftItems.filter(function (it) {
            return (it.name + ' ' + (it.meta || '')).toLowerCase().indexOf(kw) >= 0;
          });
        }
        var rightItems = all.filter(function (it) { return sel[it.id]; });

        box.querySelector('[data-total]').textContent = leftItems.length;
        box.querySelector('[data-selcount]').textContent = rightItems.length;

        box.querySelector('[data-left]').innerHTML = leftItems.length
          ? leftItems.map(function (it) {
            return '<label class="tf-row">' +
              '<input type="checkbox" data-left-check="' + it.id + '">' +
              '<span class="tf-name" style="padding-left:' + ((it.level || 0) * 14) + 'px">' + esc(it.name) + '</span>' +
              (it.meta ? '<span class="tf-meta">' + esc(it.meta) + '</span>' : '') +
            '</label>';
          }).join('')
          : '<div class="tf-empty">' + (kw ? '没有匹配项' : '无可选项') + '</div>';

        box.querySelector('[data-right]').innerHTML = rightItems.length
          ? rightItems.map(function (it) {
            var tags = activeDim === 'users' ? sourceTagsOf(it.id) : [];
            return '<div class="tf-row">' +
              '<input type="checkbox" data-right-check="' + it.id + '">' +
              '<span class="tf-name">' + esc(it.name) + '</span>' +
              (tags.length ? '<span class="tf-src">' + tags.join('/') + '</span>' : '') +
              (it.meta ? '<span class="tf-meta">' + esc(it.meta) + '</span>' : '') +
              '<span class="tf-del" data-del="' + it.id + '" title="移出">' + window.Icon('icon-x') + '</span>' +
            '</div>';
          }).join('')
          : '<div class="tf-empty">' + (activeDim === 'users' ? '暂无授权人员' : '暂无已选项') + '</div>';

        box.querySelectorAll('[data-del]').forEach(function (el) {
          el.addEventListener('click', function (ev) {
            ev.stopPropagation();
            removeIds([el.getAttribute('data-del')]);
            renderAll();
          });
        });
        box.querySelector('[data-all]').checked = false;
      }

      function renderSummary() {
        var people = idsOf(effectiveMap()).length;
        var src = [];
        if (idsOf(srcSel.orgs).length) src.push('组织 ' + idsOf(srcSel.orgs).length);
        if (idsOf(srcSel.positions).length) src.push('岗位 ' + idsOf(srcSel.positions).length);
        if (idsOf(srcSel.roles).length) src.push('角色 ' + idsOf(srcSel.roles).length);
        if (idsOf(manualOnlyMap()).length) src.push('单独添加 ' + idsOf(manualOnlyMap()).length);
        var ex = idsOf(excluded).length;
        box.querySelector('[data-summary]').innerHTML =
          '生效授权 <b class="tf-num">' + people + '</b> 人' +
          (src.length ? ' · 来源：' + src.join(' · ') : '') +
          (ex ? ' · 已单独移除 <b class="tf-num">' + ex + '</b> 人' : '');
      }

      function currentValue() {
        var out = {};
        dims.forEach(function (d) {
          out[d.key] = d.key === 'users' ? idsOf(manualOnlyMap()) : idsOf(srcSel[d.key]);
        });
        out.excluded = idsOf(excluded);
        return out;
      }

      function renderAll() {
        renderTabs();
        renderHint();
        renderLists();
        renderSummary();
        if (opts.onChange) opts.onChange(currentValue());
      }

      function moveChecked(fromKey) {
        var ids = [];
        box.querySelectorAll('[data-' + fromKey + '-check]').forEach(function (cb) {
          if (cb.checked) ids.push(cb.getAttribute('data-' + fromKey + '-check'));
        });
        return ids;
      }

      box.querySelector('[data-all]').addEventListener('change', function (e) {
        box.querySelectorAll('[data-left-check]').forEach(function (cb) { cb.checked = e.target.checked; });
      });

      box.querySelector('[data-search]').addEventListener('input', function (e) {
        keyword = e.target.value;
        renderLists();
      });

      /* 上限校验：按当前页签的已选数量计算，超出部分丢弃并提示 */
      function fitLimit(ids) {
        var max = limits[activeDim];
        if (!max) return ids;
        var unit = activeDim === 'users' ? ' 人' : ' 项';
        var left = max - countOf(activeDim);
        if (left <= 0) {
          window.toast(labelOf(activeDim) + '最多 ' + max + unit + '，请先移出部分已选项', 'error');
          return [];
        }
        if (ids.length > left) {
          window.toast(labelOf(activeDim) + '最多 ' + max + unit + '，本次仅移入 ' + left + unit, 'error');
          return ids.slice(0, left);
        }
        return ids;
      }

      /* 移入：来源维度记录选择；人员维度记为单独添加 */
      function addIds(ids) {
        ids.forEach(function (id) {
          if (activeDim === 'users') {
            manual[id] = true;
            delete excluded[id];
          } else {
            srcSel[activeDim][id] = true;
          }
        });
      }

      /* 移出：来源维度取消选择；人员维度记为显式移除 */
      function removeIds(ids) {
        if (activeDim === 'users') {
          var derived = derivedMap();
          ids.forEach(function (id) {
            if (derived[id]) excluded[id] = true;
            delete manual[id];
          });
        } else {
          ids.forEach(function (id) { delete srcSel[activeDim][id]; });
          pruneExcluded();
        }
      }

      box.querySelectorAll('[data-move]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var act = btn.getAttribute('data-move');
          if (act === 'toRight') {
            var ids = moveChecked('left');
            if (!ids.length) {
              window.toast('请先在左侧勾选要' + (activeDim === 'users' ? '授权的人员' : '移入的项'), 'error');
              return;
            }
            addIds(fitLimit(ids));
          } else if (act === 'allRight') {
            var allIds = [];
            box.querySelectorAll('[data-left-check]').forEach(function (cb) {
              allIds.push(cb.getAttribute('data-left-check'));
            });
            addIds(fitLimit(allIds));
          } else if (act === 'toLeft') {
            var rids = moveChecked('right');
            if (!rids.length) {
              window.toast('请先在右侧勾选要' + (activeDim === 'users' ? '移除的人员' : '移出的项'), 'error');
              return;
            }
            removeIds(rids);
          } else if (act === 'allLeft') {
            removeIds(idsOf(selectedOf(activeDim)));
          }
          renderAll();
        });
      });

      box.querySelector('[data-clear]').addEventListener('click', function () {
        removeIds(idsOf(selectedOf(activeDim)));
        renderAll();
      });

      renderAll();

      return {
        get: currentValue,
        /* 生效授权人员 id（人是最小颗粒） */
        people: function () { return idsOf(effectiveMap()); },
        focus: function (dim) {
          if (dim && dims.filter(function (d) { return d.key === dim; }).length) {
            activeDim = dim;
            renderAll();
          }
        }
      };
    }

    return { html: html, mount: mount };
  };

  /* ---------- Toast ---------- */
  window.toast = function (msg, type, linkText, onLink) {
    var wrap = document.querySelector('.toast-wrap');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.className = 'toast-wrap';
      document.body.appendChild(wrap);
    }
    var el = document.createElement('div');
    el.className = 'toast' + (type === 'error' ? ' error' : '');
    el.innerHTML = window.Icon(type === 'error' ? 'icon-alert' : 'icon-check-circle') + '<span>' + esc(msg) + '</span>' +
      (linkText ? '<span class="t-link">' + esc(linkText) + '</span>' : '');
    wrap.appendChild(el);
    if (linkText && onLink) {
      el.querySelector('.t-link').addEventListener('click', function () {
        onLink();
        el.remove();
      });
    }
    setTimeout(function () { el.style.opacity = '0'; setTimeout(function () { el.remove(); }, 300); }, 2600);
  };

  /* ---------- 通用容器 ---------- */
  var zSeed = 1003;

  window.openDrawer = function (opts) {
    opts = opts || {};
    var z = ++zSeed;
    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div class="drawer-overlay show" style="z-index:' + z + '"></div>' +
      '<div class="drawer" style="width:' + (opts.width || 720) + 'px;z-index:' + (z + 1) + '">' +
      '<div class="drawer-header"><h3 class="drawer-title">' + esc(opts.title || '') + '</h3>' +
      '<div class="drawer-header-actions"><button class="drawer-close" data-close>' + window.Icon('icon-x') + '</button></div></div>' +
      '<div class="drawer-body">' + (opts.body || '') + '</div>' +
      (opts.footer ? '<div class="drawer-footer">' + opts.footer + '</div>' : '') +
      '</div>';
    document.body.appendChild(wrap);
    var drawer = wrap.querySelector('.drawer');
    requestAnimationFrame(function () { drawer.classList.add('show'); });
    var closed = false;
    function close() {
      if (closed) return;
      closed = true;
      drawer.classList.remove('show');
      setTimeout(function () { wrap.remove(); }, 300);
      zSeed--;
    }
    wrap.querySelectorAll('[data-close]').forEach(function (b) {
      b.addEventListener('click', function () {
        if (opts.onBeforeClose && opts.onBeforeClose() === false) return;
        close();
      });
    });
    var api = { root: wrap, close: close };
    if (opts.onMount) opts.onMount(wrap, api);
    return api;
  };

  window.openModal = function (opts) {
    opts = opts || {};
    var z = ++zSeed;
    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div class="modal-overlay show" style="z-index:' + z + '">' +
      '<div class="modal" style="width:' + (opts.width || 640) + 'px">' +
      '<div class="modal-header"><span class="modal-title">' + esc(opts.title || '') + '</span>' +
      '<div class="modal-actions"><button class="modal-action-btn" data-close>' + window.Icon('icon-x') + '</button></div></div>' +
      '<div class="modal-body">' + (opts.body || '') + '</div>' +
      (opts.footer ? '<div class="modal-footer">' + opts.footer + '</div>' : '') +
      '</div></div>';
    document.body.appendChild(wrap);
    var overlay = wrap.querySelector('.modal-overlay');
    var closed = false;
    function close() {
      if (closed) return;
      closed = true;
      wrap.remove();
      if (opts.onClosed) opts.onClosed();
      zSeed--;
    }
    wrap.querySelectorAll('[data-close]').forEach(function (b) { b.addEventListener('click', close); });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    var api = { root: wrap, close: close };
    if (opts.onMount) opts.onMount(wrap, api);
    return api;
  };

  /* ---------- 二次确认 ---------- */
  window.confirmDialog = function (opts) {
    opts = opts || {};
    var body = '<div class="confirm-text">' + esc(opts.text || '') + '</div>' +
      (opts.impact ? '<div class="confirm-impact">' + opts.impact + '</div>' : '');
    var footer = '<button class="btn btn-default" data-close>取消</button>' +
      '<button class="btn ' + (opts.danger ? 'btn-danger' : 'btn-primary') + '" data-ok>' + esc(opts.okText || '确认') + '</button>';
    return window.openModal({
      title: opts.title || '确认操作',
      width: opts.width || 460,
      body: body,
      footer: footer,
      onMount: function (root, api) {
        root.querySelector('[data-ok]').addEventListener('click', function () {
          api.close();
          if (opts.onOk) opts.onOk();
        });
      }
    });
  };

  /* ============================================================
   * 四、左侧菜单 + 路由
   * ============================================================ */
  /* 一级菜单只有一个入口：助理 & 技能 & 连接器
     鼠标移入（或点击）后浮出二级菜单：助理 / 技能 / 连接器 */
  var MODULE_LABEL = '助理 & 技能 & 连接器';

  var MODULES = [
    { id: 'assistant', name: '助理', icon: 'icon-users', page: 'D-AT-LIST' },
    { id: 'skill', name: '技能', icon: 'icon-layers', stub: '技能' },
    { id: 'connector', name: '连接器', icon: 'icon-link', stub: '连接器' }
  ];

  var FILE_MAP = {
    'D-AT-LIST': 'pages/D-AT-LIST.js',
    'D-AT-APPR': 'pages/D-AT-LIST.js',
    'D-AT-NEWTASK': 'pages/D-AT-NEWTASK.js'
  };

  var DEFAULT_PAGE = 'D-AT-LIST';
  var loaded = {};
  var currentPage = DEFAULT_PAGE;

  var pageContent = document.getElementById('page-content');
  var sidebarEl = document.getElementById('sidebar-nav');

  /* 二级菜单（浮层）内容：助理 / 技能 / 连接器 */
  function flyoutHtml() {
    return MODULES.map(function (m) {
      var attr = m.stub ? ' data-stub="' + m.stub + '"' : ' data-page="' + m.page + '"';
      return '<div class="ls-flyout-item"' + attr + '>' +
        '<span class="ls-item-icon">' + window.Icon(m.icon) + '</span>' +
        '<span class="ls-item-name">' + m.name + '</span></div>';
    }).join('');
  }

  function renderSidebar() {
    sidebarEl.innerHTML =
      '<div class="ls-item is-new" data-new="1">' +
        '<span class="ls-item-icon">' + window.Icon('icon-plus') + '</span>' +
        '<span class="ls-item-name">新建任务</span></div>' +
      '<div class="ls-item ls-module-entry" id="moduleEntry">' +
        '<span class="ls-item-icon">' + window.Icon('icon-grid') + '</span>' +
        '<span class="ls-item-name">' + MODULE_LABEL + '</span>' +
        '<span class="ls-item-arrow">' + window.Icon('icon-chevron-right') + '</span>' +
        '<div class="ls-flyout"><div class="ls-flyout-card">' + flyoutHtml() + '</div></div>' +
      '</div>';

    var entry = sidebarEl.querySelector('#moduleEntry');
    function closeFlyout() {
      entry.classList.remove('is-open');
      entry.classList.add('suppress');
    }
    entry.addEventListener('mouseleave', function () { entry.classList.remove('suppress'); });

    /* 点击可固定展开（兼容触屏/点击习惯）；hover 由 CSS 控制 */
    entry.addEventListener('click', function (e) {
      if (e.target.closest('.ls-flyout-card')) return;
      entry.classList.remove('suppress');
      entry.classList.toggle('is-open');
    });
    document.addEventListener('click', function (e) {
      if (!entry.contains(e.target)) closeFlyout();
    });

    sidebarEl.querySelectorAll('[data-page]').forEach(function (el) {
      el.addEventListener('click', function () {
        switchPage(el.getAttribute('data-page'));
        closeFlyout();
      });
    });
    sidebarEl.querySelectorAll('[data-stub]').forEach(function (el) {
      el.addEventListener('click', function () {
        renderStub(el.getAttribute('data-stub'));
        closeFlyout();
      });
    });
    sidebarEl.querySelectorAll('[data-new]').forEach(function (el) {
      el.addEventListener('click', function () {
        STORE.session = null;
        renderTasks();
        switchPage('D-AT-NEWTASK');
      });
    });
  }

  function setActive(pageId) {
    sidebarEl.querySelectorAll('[data-page]').forEach(function (el) {
      el.classList.toggle('active', el.getAttribute('data-page') === pageId);
    });
    sidebarEl.querySelectorAll('[data-stub]').forEach(function (el) {
      el.classList.remove('active');
    });
    var entry = sidebarEl.querySelector('#moduleEntry');
    if (entry) entry.classList.toggle('has-active', !!FILE_MAP[pageId]);
  }

  /* 占位页（技能 / 连接器） */
  function renderStub(name) {
    sidebarEl.querySelectorAll('[data-page]').forEach(function (el) { el.classList.remove('active'); });
    sidebarEl.querySelectorAll('[data-stub]').forEach(function (el) {
      el.classList.toggle('active', el.getAttribute('data-stub') === name);
    });
    var entry = sidebarEl.querySelector('#moduleEntry');
    if (entry) entry.classList.add('has-active');
    pageContent.innerHTML = '<div class="page-card"><div class="page-head"><div>' +
      '<div class="page-title">' + name + '</div>' +
      '<div class="page-subtitle">该模块不在本次迭代范围内，原型聚焦「助理」的创建、共享、下架与审批链路。</div>' +
      '</div></div><div class="empty-state"><div class="empty-icon">' + window.Icon('icon-layers', 'icon-lg') + '</div>' +
      '<div class="empty-state-text">' + name + ' · 演示占位页</div></div></div>';
    window.scrollTo(0, 0);
  }

  /* 左侧任务列表 */
  function renderTasks() {
    var el = document.getElementById('taskList');
    if (!el) return;
    var list = [];
    if (STORE.session) {
      list.push({
        assistantId: STORE.session.assistantId, title: STORE.session.title,
        time: STORE.session.at, active: true
      });
    }
    list.push({ assistantId: 'E1001', title: '校招面试官提问清单整理', time: '10月23日 15:26' });
    list.push({ assistantId: 'P04', title: 'Q3 部门人效对比分析', time: '10月20日 10:11' });

    el.innerHTML = list.map(function (t, i) {
      return '<div class="ls-task-item' + (t.active ? ' active' : '') + '" data-task="' + i + '">' +
        '<span class="ls-task-icon">' + window.Icon('icon-message') + '</span>' +
        '<div class="ls-task-main"><div class="ls-task-title">' + esc(t.title) + '</div>' +
        '<div class="ls-task-time">' + esc(t.time) + '</div></div>' +
        '<span class="ls-task-more">' + window.Icon('icon-more') + '</span></div>';
    }).join('');

    el.querySelectorAll('[data-task]').forEach(function (node) {
      node.addEventListener('click', function () {
        var t = list[Number(node.getAttribute('data-task'))];
        STORE.session = { assistantId: t.assistantId, title: t.title, at: t.time };
        renderTasks();
        switchPage('D-AT-NEWTASK');
      });
    });
  }
  window.__renderTasks = renderTasks;

  function loadPage(pageId, cb) {
    if (loaded[pageId]) { cb(); return; }
    var file = FILE_MAP[pageId];
    if (!file) { pageContent.innerHTML = '<div class="empty-state">页面未找到：' + pageId + '</div>'; return; }
    var sc = document.createElement('script');
    sc.src = file + '?t=' + Date.now();
    sc.onload = function () { loaded[pageId] = true; cb(); };
    sc.onerror = function () { pageContent.innerHTML = '<div class="empty-state">页面加载失败：' + file + '</div>'; };
    document.body.appendChild(sc);
  }

  function switchPage(pageId) {
    currentPage = pageId;
    loadPage(pageId, function () {
      var render = window.__pages && window.__pages[pageId];
      if (typeof render === 'function') {
        pageContent.innerHTML = '';
        try {
          render(pageContent);
        } catch (e) {
          console.error('[render error] ' + pageId, e);
          pageContent.innerHTML = '<div class="empty-state">页面渲染异常：' + pageId + '</div>';
        }
        setActive(pageId);
        renderTasks();
        window.scrollTo(0, 0);
      } else {
        pageContent.innerHTML = '<div class="empty-state">渲染函数缺失：' + pageId + '</div>';
      }
    });
  }
  window.__switchPage = switchPage;
  window.__reload = function () { switchPage(currentPage); };

  /* ============================================================
   * 五、视角切换
   * ============================================================ */
  function applyRole() {
    var u = window.__roleUser();
    var av = document.getElementById('navAvatar');
    var un = document.getElementById('navUser');
    if (av) av.textContent = u.avatar;
    if (un) un.textContent = u.name;
  }
  var roleSelect = document.getElementById('roleSelect');
  if (roleSelect) {
    roleSelect.value = STORE.role;
    roleSelect.addEventListener('change', function () {
      STORE.role = roleSelect.value;
      localStorage.setItem('at_role', STORE.role);
      applyRole();
      window.__reload();
      window.toast('已切换为' + window.__roleUser().title + '视角');
    });
  }

  /* ============================================================
   * 六、启动
   * ============================================================ */
  window.__pages = window.__pages || {};
  renderSidebar();
  renderTasks();
  applyRole();

  /* 支持地址栏直达，便于评审时分享单个页面：
     index.html?page=D-AT-NEWTASK&assistant=E1001 */
  var qs = new URLSearchParams(location.search);
  var qPage = qs.get('page');
  var qAssistant = qs.get('assistant') || qs.get('assistant');
  if (qAssistant) {
    var hit = STORE.assistants.filter(function (e) { return e.id === qAssistant; })[0];
    if (hit) {
      STORE.session = {
        assistantId: hit.id, title: '与' + hit.name + '的对话',
        at: new Date().toLocaleString('zh-CN')
      };
      renderTasks();
    }
  }
  switchPage(FILE_MAP[qPage] ? qPage : DEFAULT_PAGE);
})();
