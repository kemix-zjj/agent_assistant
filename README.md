# 数智助理 · 助理团助理创建与共享授权

把「平台预置助理」扩展为「平台预置 + 用户自建 + 授权共享」，用一套表单让业务员工把经验做成可召唤的助理，用一套授权与审批机制让助理在可控边界内流转。

## 快速导航

| 内容 | 位置 |
|------|------|
| 需求说明书 v1.2 | [docs/需求说明书-v1.2.md](docs/需求说明书-v1.2.md) |
| 总体架构设计 | [docs/01-总体架构设计.md](docs/01-总体架构设计.md) |
| 数据库设计 | [docs/02-数据库设计.md](docs/02-数据库设计.md) |
| 接口设计 | [docs/03-接口设计.md](docs/03-接口设计.md) |
| UI 原型（可直接运行） | [prototype/index.html](prototype/index.html) |

## 目录结构

```
20261026-助理管理授权/
├── docs/           设计与需求文档（4 份）
├── prototype/      UI 原型，纯静态，双击 index.html 即可运行
├── web/            前端工程（本期以原型为基线改造接入 API）
├── server/         后端工程（Python + FastAPI + PostgreSQL）
└── deploy/         部署物（Dockerfile / compose / 环境变量样例）
```

### docs/

| 文档 | 内容 |
|------|------|
| `需求说明书-v1.2.md` | 13 个功能点、EARS 需求列表、验收标准 |
| `01-总体架构设计.md` | 分层架构、模块划分、关键设计决策、权限模型、状态机、核心链路时序 |
| `02-数据库设计.md` | ER 图、15 张表 DDL、索引与性能、数据一致性规则 |
| `03-接口设计.md` | 29 个接口清单、出入参、28 个错误码、页面映射 |

### prototype/

UI 原型，纯静态无构建依赖，双击 `index.html` 即可评审。

| 路径 | 说明 |
|------|------|
| `index.html` | SPA 入口（图标精灵 + 飞书风格侧栏 + 地址栏直达） |
| `css/common.css` | 设计系统基础样式与令牌 |
| `css/assistant.css` | 助理业务样式（卡片栅格、状态标签、三步向导） |
| `js/common.js` | 原型运行时（Mock 数据、路由、抽屉/弹窗/Toast、四维穿梭框） |
| `pages/D-AT-LIST.js` | 助理列表页（创建 / 详情 / 召唤 / 删除 / 共享范围 / 审批中心） |
| `pages/D-AT-NEWTASK.js` | 新建任务页（召唤后的对话入口） |
| `_legacy/` | 历史 v2 草稿归档，不参与运行 |

**评审直达**
- 助理列表：`prototype/index.html`
- 新建任务（携带助理）：`prototype/index.html?page=D-AT-NEWTASK&assistant=E1001`
- 公司管理员审批视图：侧栏「视角」切换为「公司管理员 · 王建国」后，点击助理页右上角「审批中心」

### server/

```
server/
├── app/
│   ├── main.py              FastAPI 应用装配入口
│   ├── api/v1/              路由层（参数校验 + 权限注解 + 响应包装）
│   ├── core/                配置、鉴权、异常、日志、幂等、分页
│   ├── models/              SQLAlchemy ORM 模型（对应 02-数据库设计）
│   ├── schemas/             Pydantic 出入参模型
│   ├── services/            领域服务（助理/共享/审批/订阅/范围展开/AI）
│   └── repositories/        数据访问层
├── migrations/              Alembic 迁移脚本
└── tests/                   单元测试 + 接口测试
```

分层约束：`api → services → repositories → models`，路由层不写业务判断，服务层不依赖 HTTP 对象，仓储层不写业务规则。

### web/

```
web/src/
├── api/            接口封装（与 03-接口设计一一对应）
├── components/     通用组件（抽屉/弹窗/四维穿梭框/标签/Toast）
└── views/          页面级视图（助理列表/新建任务/审批中心）
```

## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | Python 3.11 · FastAPI · SQLAlchemy 2.0 · Alembic |
| 数据库 | PostgreSQL 15（主备 + 每日全量备份） |
| 缓存 | Redis（幂等键、待审批角标、会话） |
| 前端 | Vue 3.5 · TypeScript · Vite 6 · Element Plus · Pinia · Vue Router |
| 存储 | 对象存储（头像，预签名直传） |

## 本期范围

**做**：助理手动创建（5 页签）、列表查询（全部 / 我的 / 共享）、召唤、编辑、删除、共享提交（范围授权 / 公开）、共享状态查询、被拒后重新提交、共享范围调整、审批中心（列表 / 卡片双视图）、审批通过 / 拒绝、共享助理移除与重新订阅、AI 生成（描述 / 标签 / 提示词 / 快速问题）。

**不做**：助理停用 / 复制 / 导出、跨公司共享、审批历史与多级流转、独立授权管理后台、分类字典后台、提示词版本回滚、SKILL/MCP/知识库自身配置、效果统计报表、移动端适配。

> 原型中另有「下架申请」「第三方接入」「版本记录详情」等能力，需求说明书 v1.2 已列为非范围；架构上仅做字段与枚举预留，不建接口与流程。详见 [总体架构设计 §4.2](docs/01-总体架构设计.md)。

## 本地启动

```bash
# 后端（Python）
cd server
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 前端（Vue 3 + TS，开发端口 5173，/api 代理到 8000）
cd web
npm install
npm run dev
```

## 待确认事项

三份设计文档末尾各有一节「待确认事项」，共 12 项（Q-01 ~ Q-12），涉及范围筛选口径、公开模式授权落库方式、批量提交事务语义等。建议评审时逐项过一遍。
