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
├── web/            前端工程（Vue 3 + Vite，已接入真实接口）
├── server/         后端工程（Python + FastAPI + MySQL 8.0）
└── deploy/         部署物（MySQL 建表脚本）
```

### docs/

| 文档 | 内容 |
|------|------|
| `需求说明书-v1.2.md` | 13 个功能点、EARS 需求列表、验收标准 |
| `01-总体架构设计.md` | 分层架构、模块划分、关键设计决策、权限模型、状态机、核心链路时序 |
| `02-数据库设计.md` | ER 图、14 张表 DDL、索引与性能、数据一致性规则 |
| `03-接口设计.md` | 29 个接口清单、出入参、26 个错误码、页面映射 |

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
│   ├── api/                 健康检查 + v1 路由层（参数校验 + 统一响应包装）
│   ├── core/                 配置、数据库、鉴权、异常、日志、分页
│   ├── models/              SQLAlchemy ORM 模型（对应 02-数据库设计，14 张表）
│   ├── schemas/             Pydantic 出入参模型
│   ├── services/            领域服务（分类、助理 CRUD、共享提交/范围展开、审批中心、资源、召唤订阅、AI、头像）
│   └── repositories/        数据访问层
├── migrations/              Alembic 迁移配置（建表以 deploy/mysql 脚本为准）
├── .env.example             环境变量样例，复制为 .env 后填写数据库密码
├── alembic.ini
├── scripts/                 check_schema、purge_test_data、clean_orphan_audit、reset_dev_data、e2e 验证
└── tests/                   接口测试（骨架 / 助理 CRUD / 共享 / 审批 / 资源召唤订阅 AI 头像）
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
| 后端 | Python 3.10+ · FastAPI · SQLAlchemy 2.0 · Alembic |
| 数据库 | MySQL 8.0（主备 + 每日全量备份） |
| 幂等 | 审批决策与订阅操作以条件更新 + 状态回放保证，重复请求返回首次结果（无独立幂等表） |
| 前端 | Vue 3.5 · TypeScript · Vite 6 · Element Plus · Pinia · Vue Router |
| 存储 | 对象存储（头像，预签名直传；当前返回占位地址，待接入 OSS/S3） |

## 本期范围

**做**：助理手动创建（5 页签）、列表查询（全部 / 我的 / 共享）、召唤、编辑、删除、共享提交（范围授权 / 公开）、共享状态查询、被拒后重新提交、共享范围调整、审批中心（列表 / 卡片双视图）、审批通过 / 拒绝、共享助理移除与重新订阅、AI 生成（描述 / 标签 / 提示词 / 快速问题）。

**不做**：助理停用 / 复制 / 导出、跨公司共享、审批历史与多级流转、独立授权管理后台、分类字典后台、提示词版本回滚、SKILL/MCP/知识库自身配置、效果统计报表、移动端适配。

> 原型中另有「下架申请」「第三方接入」「版本记录详情」等能力，需求说明书 v1.2 已列为非范围；架构上仅做字段与枚举预留，不建接口与流程。详见 [总体架构设计 §4.2](docs/01-总体架构设计.md)。

## 本地运行

### 1. 环境要求

| 项 | 版本 | 说明 |
|----|------|------|
| Python | 3.10+ | 本机为 `D:\Miniconda\envs\Agent\python.exe` |
| Node.js | 18+ | 随附 npm |
| MySQL | 8.0 | 默认 `127.0.0.1:3306`，库名 `assistant` |

### 2. 初始化数据库

```powershell
# MySQL 8.0：执行建库建表脚本（14 张表 + 演示数据）
mysql -u root -p < deploy/mysql/assistant_mysql.sql
```

### 3. 后端（FastAPI，端口 8000）

```powershell
conda activate Agent          # 本项目依赖装在 Agent 环境
cd e:\agent-code\agent_expert\server
copy .env.example .env        # 填写 DB_PASSWORD
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
```

> 必须先切到 `Agent` 环境。`python` 默认指向 conda 的 base 环境（`D:\Miniconda\python.exe`），那里没装本项目依赖，直接运行会报 `No module named uvicorn`。不想激活环境时，用绝对路径启动：`D:\Miniconda\envs\Agent\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app`。

| 用途 | 地址 |
|------|------|
| 接口文档（Swagger UI） | http://127.0.0.1:8000/docs |
| 接口文档（ReDoc） | http://127.0.0.1:8000/redoc |
| OpenAPI 描述文件 | http://127.0.0.1:8000/openapi.json |
| 健康检查 | http://127.0.0.1:8000/health |

> 以上三个文档地址均由 FastAPI 从代码自动生成，不是手写文件；生成机制见 [03-接口设计 §1.2](docs/03-接口设计.md#12-接口文档的生成方式)。

登录态由请求头模拟（网关接入前）：`X-User-Id`、`X-Company-Id`，可选 `X-User-Name`、`X-User-Dept`（中文需 UTF-8 百分号编码，服务端自动解码）。`X-User-Id=9001` 视为公司管理员，其余为普通员工。

主数据（组织 / 角色 / 岗位 / 人员）当前由 [master_data.py](server/app/services/master_data.py) 内置演示数据提供，通过 `Employee.login_id` 把登录账号映射到人员（如 `2001` → `u1 李静`），用于「共享助理」列表与授权匹配。接入真实主数据服务时，替换该模块的查询函数即可，路由层无需改动。

AI 生成（`POST /ai/generate`）当前为确定性模板实现，未接大模型中台；输出符合各字段校验规则（描述 10-200 字、标签 ≤5 个且单个 ≤8 字、提示词 ≤4000 字、快速问题 ≤6 条）。接入时替换 [ai_service.py](server/app/services/ai_service.py) 的 `_generate` / `_polish` 即可，接口签名不变。

### 4. 前端（Vue 3 + TS，端口 5173，`/api` 代理到 8000）

```powershell
cd e:\agent-code\agent_expert\web
npm install
npm run dev
```

> 前端默认走真实接口（`VITE_USE_MOCK=false`）。若需离线演示原型，把该变量改为 `true` 即可切回 Mock，视图层无需改动。代理目标由 `web/.env.development` 的 `VITE_PROXY_TARGET` 控制，默认 `http://127.0.0.1:8000`。

### 5. 常用命令

| 目的 | 命令 | 工作目录 |
|------|------|----------|
| 启动后端 | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app` | `server/` |
| 启动前端 | `npm run dev` | `web/` |
| 后端接口测试（99 项） | `python -m pytest -q` | `server/` |
| 前端类型检查 | `npm run type-check` | `web/` |
| 前端构建 | `npm run build` | `web/` |

> 后端 `--reload` 在本机偶发不生效（改过模型或删过表后接口仍按旧代码报错）。遇到「代码已改但行为未变」，先看控制台有没有 `Reloading...`，没有就手动重启后端进程。

## 待确认事项

三份设计文档末尾各有一节「待确认事项」，共 12 项（Q-01 ~ Q-12），涉及范围筛选口径、公开模式授权落库方式、批量提交事务语义等。建议评审时逐项过一遍。
