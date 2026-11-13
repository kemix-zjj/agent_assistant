-- ============================================================
-- 助理团助理创建与共享授权 · MySQL 8.0 建库建表脚本
-- 来源：docs/02-数据库设计.md（MySQL 8.0）
-- 表数量：14 张（业务 12 张 + 支撑 2 张）
-- 转换说明：
--   1) BIGSERIAL → BIGINT AUTO_INCREMENT；TIMESTAMPTZ → DATETIME；
--      BOOLEAN → TINYINT(1)；JSONB → JSON；COMMENT ON → 列/表 COMMENT
--   2) PG 部分唯一索引（带 WHERE）→ MySQL 用 STORED 生成列 + 唯一索引等价实现
--      （唯一索引允许多个 NULL，故生效行标记为 1，非生效行为 NULL）
--   3) PG 部分普通索引（带 WHERE）→ 去掉 WHERE，保留同列组合索引
--   4) sys_audit_log 分区键须包含在主键中：PRIMARY KEY (id, created_at)
-- 执行：mysql -u root -p < assistant_mysql.sql
-- ============================================================

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS `assistant`
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE `assistant`;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `sys_audit_log`;
DROP TABLE IF EXISTS `assistant_summon`;
DROP TABLE IF EXISTS `approval`;
DROP TABLE IF EXISTS `assistant_grant`;
DROP TABLE IF EXISTS `share_scope_item`;
DROP TABLE IF EXISTS `share_scope`;
DROP TABLE IF EXISTS `assistant_version_history`;
DROP TABLE IF EXISTS `assistant_quick_question`;
DROP TABLE IF EXISTS `assistant_tag`;
DROP TABLE IF EXISTS `assistant_kb_rel`;
DROP TABLE IF EXISTS `assistant_mcp_rel`;
DROP TABLE IF EXISTS `assistant_skill_rel`;
DROP TABLE IF EXISTS `assistant`;
DROP TABLE IF EXISTS `assistant_category`;

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- 4.1 assistant_category · 助理分类字典
-- ------------------------------------------------------------
CREATE TABLE `assistant_category` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `company_id`  BIGINT       NOT NULL COMMENT '公司 ID，多租户隔离字段',
    `name`        VARCHAR(10)  NOT NULL COMMENT '分类名称，≤10 字符，公司内唯一',
    `sort_no`     INT          NOT NULL DEFAULT 0 COMMENT '排序号，升序展示，值越小越靠前',
    `is_builtin`  TINYINT      NOT NULL DEFAULT 0 COMMENT '是否系统内置，内置分类不允许删除',
    `created_by`  BIGINT       NULL COMMENT '创建人用户 ID；系统初始化数据为空',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `deleted_at`  DATETIME     NULL COMMENT '逻辑删除时间，非空表示已删除',
    -- 等价 PG: CREATE UNIQUE INDEX ... WHERE deleted_at IS NULL
    `active_flag` TINYINT GENERATED ALWAYS AS (IF(`deleted_at` IS NULL, 1, NULL)) STORED
                  COMMENT '生效行标记生成列：未删除为 1、已删除为 NULL，配合唯一索引实现部分唯一',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_category_company_name` (`company_id`, `name`, `active_flag`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '助理分类字典；内置协同办公/人资/智慧云仓/环安/经营管理，管理员可在表单内新增';

-- ------------------------------------------------------------
-- 4.2 assistant · 助理主表
-- ------------------------------------------------------------
CREATE TABLE `assistant` (
    `id`                 BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `company_id`         BIGINT       NOT NULL COMMENT '公司 ID，多租户隔离字段',
    `name`               VARCHAR(20)  NOT NULL COMMENT '昵称，2-20 字符，公司内唯一',
    `avatar_type`        VARCHAR(10)  NOT NULL DEFAULT 'char'
                         COMMENT 'char=预置字符头像，image=本地上传（2MB 内 image/*）',
    `avatar_char`        VARCHAR(2)   NULL COMMENT '预置字符头像字符，avatar_type=char 时使用',
    `avatar_url`         VARCHAR(512) NULL COMMENT '上传头像地址，avatar_type=image 时使用',
    `avatar_color`       VARCHAR(16)  NOT NULL DEFAULT '#3685F2' COMMENT '头像背景色，十六进制色值如 #3685F2',
    `description`        VARCHAR(200) NOT NULL COMMENT '描述，10-200 字符，列表截断 60 字',
    `category_id`        BIGINT       NOT NULL COMMENT '所属分类 ID，外键指向 assistant_category.id',
    `source`             VARCHAR(16)  NOT NULL
                         COMMENT 'platform 平台内置 / custom 自建 / thirdparty 第三方接入（预留）；shared 为查询视图，不落库',
    `owner_user_id`      BIGINT       NULL COMMENT '创建人；平台内置助理为空',
    `owner_name`         VARCHAR(64)  NULL COMMENT '创建人姓名快照；平台内置助理为空',
    `owner_dept_name`    VARCHAR(128) NULL COMMENT '创建人所属部门名称快照；平台内置助理为空',
    `prompt`             TEXT         NOT NULL COMMENT '提示词，必填，≤4000 字符',
    `share_status`       VARCHAR(16)  NOT NULL DEFAULT 'unshared'
                         COMMENT '共享状态：unshared 未共享 / pending 审批中 / approved 已共享 / rejected 已拒绝 / offline_pending 下架审批中 / offline 已下架',
    `pending_type`       VARCHAR(16)  NULL
                         COMMENT '审批子类：share 共享审批 / change 调整审批 / scope 授权审批 / offline 下架审批；仅审批中有值',
    `reject_type`        VARCHAR(16)  NULL
                         COMMENT '拒绝子类：share / change / scope / offline；仅已拒绝有值',
    `has_shared`         TINYINT      NOT NULL DEFAULT 0
                         COMMENT '是否曾共享成功过：决定版本号生成口径（首次记 V1.0.0）与删除资格',
    `version`            VARCHAR(16)  NOT NULL DEFAULT '' COMMENT '当前版本号，V{主版本}.{次版本}.{尾号}，如 V1.0.0；空串表示「未发布」，仅在审批通过时推进',
    `authorized_count`   INT          NOT NULL DEFAULT 0 COMMENT '已生效授权人数，冗余字段，由 assistant_grant 统计回写',
    `offline_reason`     VARCHAR(200) NULL COMMENT '下架原因，仅下架审批中 / 已下架有值',
    `last_reject_reason` VARCHAR(200) NULL COMMENT '最近一次审批拒绝原因，仅 rejected 状态有值',
    `last_approver_name` VARCHAR(64)  NULL COMMENT '最近一次审批人姓名',
    `last_approve_time`  DATETIME     NULL COMMENT '最近一次审批完成时间',
    `created_by`         BIGINT       NOT NULL COMMENT '创建人用户 ID，平台内置助理为 0（系统）',
    `created_at`         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    `deleted_at`         DATETIME     NULL COMMENT '逻辑删除；删除后关联授权置 invalid、待审批单置 terminated',
    -- 等价 PG: uk_assistant_company_name ... WHERE deleted_at IS NULL
    `active_flag`        TINYINT GENERATED ALWAYS AS (IF(`deleted_at` IS NULL, 1, NULL)) STORED
                         COMMENT '生效行标记生成列：未删除为 1、已删除为 NULL，配合唯一索引实现部分唯一',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_assistant_company_name` (`company_id`, `name`, `active_flag`),
    KEY `idx_assistant_list_mine` (`company_id`, `owner_user_id`, `created_at` DESC),
    KEY `idx_assistant_list_platform` (`company_id`, `category_id`, `created_at` DESC),
    KEY `idx_assistant_status` (`company_id`, `share_status`),
    CONSTRAINT `fk_assistant_category` FOREIGN KEY (`category_id`) REFERENCES `assistant_category` (`id`),
    CONSTRAINT `ck_assistant_avatar_type` CHECK (`avatar_type` IN ('char', 'image')),
    CONSTRAINT `ck_assistant_source` CHECK (`source` IN ('platform', 'custom', 'thirdparty')),
    CONSTRAINT `ck_assistant_share_status` CHECK (`share_status` IN ('unshared', 'pending', 'approved', 'rejected', 'offline_pending', 'offline')),
    CONSTRAINT `ck_assistant_pending_type` CHECK (`pending_type` IS NULL OR `pending_type` IN ('share', 'change', 'scope', 'offline')),
    CONSTRAINT `ck_assistant_reject_type` CHECK (`reject_type` IS NULL OR `reject_type` IN ('share', 'change', 'scope', 'offline'))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '助理（页面称「助理」「数字员工」）主表';

-- ------------------------------------------------------------
-- 4.3 ~ 4.5 能力组成关联表（SKILL / MCP / 知识库）
-- ------------------------------------------------------------
CREATE TABLE `assistant_skill_rel` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `assistant_id`     BIGINT       NOT NULL COMMENT '助理 ID，外键指向 assistant.id，级联删除',
    `resource_id`   VARCHAR(64)  NOT NULL COMMENT 'SKILL 资源 ID，来源为平台技能中心',
    `resource_name` VARCHAR(128) NOT NULL COMMENT 'SKILL 资源名称快照，用于列表直接展示',
    `sort_no`       INT          NOT NULL DEFAULT 0 COMMENT '展示顺序，按保存时选择顺序写入',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_assistant_skill` (`assistant_id`, `resource_id`),
    CONSTRAINT `fk_skill_assistant` FOREIGN KEY (`assistant_id`) REFERENCES `assistant` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '助理挂载的 SKILL，单个助理上限 20 个，保存时校验资源在线';

CREATE TABLE `assistant_mcp_rel` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `assistant_id`     BIGINT       NOT NULL COMMENT '助理 ID，外键指向 assistant.id，级联删除',
    `resource_id`   VARCHAR(64)  NOT NULL COMMENT 'MCP 服务资源 ID，来源为平台 MCP 中心',
    `resource_name` VARCHAR(128) NOT NULL COMMENT 'MCP 服务名称快照，用于列表直接展示',
    `resource_type` VARCHAR(32)  NULL COMMENT 'MCP 服务类型，如 http / sse / stdio',
    `sort_no`       INT          NOT NULL DEFAULT 0 COMMENT '展示顺序，按保存时选择顺序写入',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_assistant_mcp` (`assistant_id`, `resource_id`),
    CONSTRAINT `fk_mcp_assistant` FOREIGN KEY (`assistant_id`) REFERENCES `assistant` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '助理挂载的 MCP 服务，单个助理上限 20 个';

CREATE TABLE `assistant_kb_rel` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `assistant_id`     BIGINT       NOT NULL COMMENT '助理 ID，外键指向 assistant.id，级联删除',
    `resource_id`   VARCHAR(64)  NOT NULL COMMENT '知识库资源 ID，来源为平台知识库',
    `resource_name` VARCHAR(128) NOT NULL COMMENT '知识库名称快照，用于列表直接展示',
    `sort_no`       INT          NOT NULL DEFAULT 0 COMMENT '展示顺序，按保存时选择顺序写入',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_assistant_kb` (`assistant_id`, `resource_id`),
    CONSTRAINT `fk_kb_assistant` FOREIGN KEY (`assistant_id`) REFERENCES `assistant` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '助理关联的知识库，单个助理上限 10 个，需校验当前用户访问权限';

-- ------------------------------------------------------------
-- 4.6 assistant_tag · 助理自定义标签
-- ------------------------------------------------------------
CREATE TABLE `assistant_tag` (
    `id`         BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `assistant_id`  BIGINT      NOT NULL COMMENT '助理 ID，外键指向 assistant.id，级联删除',
    `name`       VARCHAR(8)  NOT NULL COMMENT '标签名，1-8 字符；同一助理内唯一',
    `sort_no`    INT         NOT NULL DEFAULT 0 COMMENT '展示顺序，按保存时标签输入顺序写入',
    `created_at` DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_assistant_tag` (`assistant_id`, `name`),
    KEY `idx_tag_name` (`name`),
    CONSTRAINT `fk_tag_assistant` FOREIGN KEY (`assistant_id`) REFERENCES `assistant` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '助理自定义标签；单个助理上限 5 个，单个标签 1-8 字符，去重，支持 AI 生成（REQ-EXP-AI-003/004）与列表按标签模糊搜索';

-- ------------------------------------------------------------
-- 4.7 assistant_quick_question · 召唤快速问题
-- ------------------------------------------------------------
CREATE TABLE `assistant_quick_question` (
    `id`         BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `assistant_id`  BIGINT       NOT NULL COMMENT '助理 ID，外键指向 assistant.id，级联删除',
    `content`    VARCHAR(200) NOT NULL COMMENT '快速问题内容，≤200 字符，同一助理内去重',
    `sort_no`    INT          NOT NULL DEFAULT 0 COMMENT '展示顺序，升序排列，值越小越靠前',
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_qq_assistant` (`assistant_id`, `sort_no`),
    CONSTRAINT `fk_qq_assistant` FOREIGN KEY (`assistant_id`) REFERENCES `assistant` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '召唤后欢迎区展示的快速问题，上限 6 条，去重';

-- ------------------------------------------------------------
-- 4.8 assistant_version_history · 版本与操作记录
-- ------------------------------------------------------------
CREATE TABLE `assistant_version_history` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `assistant_id`     BIGINT       NOT NULL COMMENT '助理 ID，外键指向 assistant.id，级联删除',
    `version`       VARCHAR(16)  NOT NULL COMMENT '记录时的版本号，如 V1.0.0；未发布阶段为空串',
    `action`        VARCHAR(32)  NOT NULL COMMENT '操作类型：create 创建 / update 编辑 / share_submit 共享提交 / share_approve 共享审批通过 / share_reject 共享审批被拒 / change_submit 提交变更审批 / change_approve 变更审批通过 / change_reject 变更审批被拒 / scope_change 授权范围变更 / scope_reject 授权范围变更被拒 / offline_submit 提交下架 / offline_approve 下架生效 / offline_reject 下架被拒 / delete 删除',
    `operator_id`   BIGINT       NULL COMMENT '操作人用户 ID；系统自动记录（如审批回写）为空',
    `operator_name` VARCHAR(64)  NOT NULL COMMENT '操作人姓名快照；系统记录填「系统」',
    `remark`        VARCHAR(200) NULL COMMENT '操作备注，如审批意见摘要、调整说明',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    PRIMARY KEY (`id`),
    KEY `idx_version_assistant` (`assistant_id`, `created_at` DESC),
    CONSTRAINT `fk_version_assistant` FOREIGN KEY (`assistant_id`) REFERENCES `assistant` (`id`) ON DELETE CASCADE,
    CONSTRAINT `ck_version_action` CHECK (`action` IN ('create', 'update', 'share_submit', 'share_approve', 'share_reject', 'change_submit', 'change_approve', 'change_reject', 'scope_change', 'scope_reject', 'offline_submit', 'offline_approve', 'offline_reject', 'delete'))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '助理版本与操作流水，用于详情页版本记录展示；不存配置快照，不支持回滚';

-- ------------------------------------------------------------
-- 4.9 share_scope · 共享范围快照（主）
-- ------------------------------------------------------------
CREATE TABLE `share_scope` (
    `id`             BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `company_id`     BIGINT      NOT NULL COMMENT '公司 ID，多租户隔离字段',
    `assistant_id`      BIGINT      NOT NULL COMMENT '助理 ID，外键指向 assistant.id',
    `approval_id`    BIGINT      NULL COMMENT '为空且 stage=effective 表示管理员直接配置（平台内置助理 / 管理员范围直改）',
    `scope_mode`     VARCHAR(16) NOT NULL DEFAULT 'RANGE' COMMENT '范围模式：RANGE 指定组织/角色/岗位/人员 / PUBLIC 全员公开',
    `stage`          VARCHAR(16) NOT NULL COMMENT '范围阶段：requested 提交时申请范围 / adjusted 审批前管理员调整 / effective 最终生效范围',
    `org_count`      INT         NOT NULL DEFAULT 0 COMMENT '组织维度选择数量',
    `role_count`     INT         NOT NULL DEFAULT 0 COMMENT '角色维度选择数量',
    `position_count` INT         NOT NULL DEFAULT 0 COMMENT '岗位维度选择数量',
    `user_count`     INT         NOT NULL DEFAULT 0 COMMENT '人员维度直接选择数量',
    `grant_total`    INT         NOT NULL DEFAULT 0 COMMENT '展开后授权人数；PUBLIC 模式下为公司在职人数',
    `created_by`     BIGINT      NOT NULL COMMENT '创建人用户 ID；系统生成时填 0',
    `created_at`     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_scope_assistant_stage` (`assistant_id`, `stage`, `created_at` DESC),
    KEY `idx_scope_approval` (`approval_id`),
    CONSTRAINT `fk_scope_assistant` FOREIGN KEY (`assistant_id`) REFERENCES `assistant` (`id`),
    CONSTRAINT `ck_scope_mode` CHECK (`scope_mode` IN ('RANGE', 'PUBLIC')),
    CONSTRAINT `ck_scope_stage` CHECK (`stage` IN ('requested', 'adjusted', 'effective'))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '共享范围快照；requested=提交时申请范围，adjusted=审批前管理员调整，effective=最终生效范围';

-- ------------------------------------------------------------
-- 4.10 share_scope_item · 共享范围快照明细
-- ------------------------------------------------------------
CREATE TABLE `share_scope_item` (
    `id`         BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `scope_id`   BIGINT       NOT NULL COMMENT '范围快照 ID，外键指向 share_scope.id，级联删除',
    `dim`        VARCHAR(16)  NOT NULL COMMENT '范围维度：org 组织 / role 角色 / position 岗位 / user 人员',
    `item_id`    VARCHAR(64)  NOT NULL COMMENT '外部主数据 ID（组织/角色/岗位/人员），不做外键，来源为主数据平台',
    `item_name`  VARCHAR(128) NOT NULL COMMENT '维度项名称快照（组织/角色/岗位/人员名称），用于审批详情展示',
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_scope_item` (`scope_id`, `dim`, `item_id`),
    KEY `idx_scope_item_scope` (`scope_id`),
    CONSTRAINT `fk_scope_item_scope` FOREIGN KEY (`scope_id`) REFERENCES `share_scope` (`id`) ON DELETE CASCADE,
    CONSTRAINT `ck_scope_item_dim` CHECK (`dim` IN ('org', 'role', 'position', 'user'))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '范围快照的四维原始选择；组织/角色/岗位仅用于批量展开人员，最终生效颗粒为 user';

-- ------------------------------------------------------------
-- 4.11 assistant_grant · 人员级授权与订阅关系
-- ------------------------------------------------------------
CREATE TABLE `assistant_grant` (
    `id`               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `company_id`       BIGINT       NOT NULL COMMENT '公司 ID，多租户隔离字段',
    `assistant_id`        BIGINT       NOT NULL COMMENT '助理 ID，外键指向 assistant.id',
    `user_id`          VARCHAR(64)  NOT NULL COMMENT '被授权用户 ID，来源为主数据平台',
    `user_name`        VARCHAR(64)  NOT NULL COMMENT '被授权用户姓名快照',
    `dept_name`        VARCHAR(128) NULL COMMENT '被授权用户所属部门名称快照',
    `grant_status`     VARCHAR(16)  NOT NULL DEFAULT 'valid' COMMENT '授权状态：valid 生效 / invalid 失效（助理删除或范围调整后失效）',
    `subscribe_status` VARCHAR(16)  NOT NULL DEFAULT 'subscribed'
                       COMMENT '被授权方自主开关：subscribed 已订阅 / removed 已移除；移除不触发审批',
    `source_scope_id`  BIGINT       NULL COMMENT '来源范围快照 ID，外键指向 share_scope.id',
    `grant_time`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                       COMMENT '授权生效时间，共享助理列表按其倒序排列',
    `subscribe_time`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最近一次订阅/移除操作时间',
    `updated_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_grant_assistant_user` (`assistant_id`, `user_id`),
    KEY `idx_grant_user_sub` (`company_id`, `user_id`, `subscribe_status`),
    KEY `idx_grant_assistant` (`assistant_id`, `grant_status`),
    CONSTRAINT `fk_grant_assistant` FOREIGN KEY (`assistant_id`) REFERENCES `assistant` (`id`),
    CONSTRAINT `fk_grant_scope` FOREIGN KEY (`source_scope_id`) REFERENCES `share_scope` (`id`),
    CONSTRAINT `ck_grant_status` CHECK (`grant_status` IN ('valid', 'invalid')),
    CONSTRAINT `ck_grant_subscribe` CHECK (`subscribe_status` IN ('subscribed', 'removed'))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '授权范围展开后的人员级关系；被授权方的「共享助理」列表以此表为准';

-- ------------------------------------------------------------
-- 4.12 approval · 审批单
-- ------------------------------------------------------------
CREATE TABLE `approval` (
    `id`                 BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `approval_no`        VARCHAR(32)  NOT NULL COMMENT '审批单号，全局唯一，供页面展示与检索',
    `batch_no`           VARCHAR(32)  NULL COMMENT '批量勾选 N 个助理提交时共享同一批次号，落库为 N 条审批单',
    `company_id`         BIGINT       NOT NULL COMMENT '公司 ID，多租户隔离字段',
    `approval_type`      VARCHAR(16)  NOT NULL DEFAULT 'share' COMMENT '审批类型：share 共享申请 / scope 授权申请 / change 调整申请 / offline 下架申请',
    `assistant_id`          BIGINT       NOT NULL COMMENT '助理 ID，外键指向 assistant.id',
    `assistant_version`     VARCHAR(16)  NOT NULL COMMENT '提交时的助理版本快照，用于审批详情识别配置已变更',
    `status`             VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT '审批状态：pending 待审批 / approved 通过 / rejected 拒绝 / terminated 已终止',
    `submitter_id`       BIGINT       NOT NULL COMMENT '提交人用户 ID',
    `submitter_name`     VARCHAR(64)  NOT NULL COMMENT '提交人姓名快照',
    `submitter_dept`     VARCHAR(128) NULL COMMENT '提交人所属部门名称快照',
    `submit_time`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '提交时间',
    `change_note`        VARCHAR(200) NULL COMMENT '申请说明 / 变更说明，审批详情展示',
    `requested_scope_id` BIGINT       NULL COMMENT '提交时申请的范围快照 ID，外键指向 share_scope.id',
    `final_scope_id`     BIGINT       NULL COMMENT '审批通过后实际生效的范围快照（含管理员调整）；等于 requested 表示未调整',
    `approver_id`        BIGINT       NULL COMMENT '审批人用户 ID，未审批时为空',
    `approver_name`      VARCHAR(64)  NULL COMMENT '审批人姓名快照，未审批时为空',
    `approve_time`       DATETIME     NULL COMMENT '审批完成时间，未审批时为空',
    `reject_reason`      VARCHAR(200) NULL COMMENT '仅 rejected 状态有值，1-200 字符，必填',
    `created_at`         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    -- 等价 PG: uk_approval_pending_assistant ... WHERE status = 'pending'
    -- 保证同一助理同一时间只允许一条待审批申请（REQ-SHR-SUBMIT-011）
    `pending_flag`       TINYINT GENERATED ALWAYS AS (IF(`status` = 'pending', 1, NULL)) STORED
                         COMMENT '待审批标记生成列：status=pending 为 1、其他状态为 NULL，配合唯一索引保证单助理仅一条待审批单',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_approval_no` (`approval_no`),
    UNIQUE KEY `uk_approval_pending_assistant` (`assistant_id`, `pending_flag`),
    KEY `idx_approval_pending_list` (`company_id`, `status`, `submit_time`),
    KEY `idx_approval_batch` (`batch_no`),
    KEY `idx_approval_assistant` (`assistant_id`, `submit_time` DESC),
    CONSTRAINT `fk_approval_assistant` FOREIGN KEY (`assistant_id`) REFERENCES `assistant` (`id`),
    CONSTRAINT `fk_approval_req_scope` FOREIGN KEY (`requested_scope_id`) REFERENCES `share_scope` (`id`),
    CONSTRAINT `fk_approval_final_scope` FOREIGN KEY (`final_scope_id`) REFERENCES `share_scope` (`id`),
    CONSTRAINT `ck_approval_type` CHECK (`approval_type` IN ('share', 'scope', 'change', 'offline')),
    CONSTRAINT `ck_approval_status` CHECK (`status` IN ('pending', 'approved', 'rejected', 'terminated'))
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '共享审批单；实现 share 共享申请、scope 授权申请、change 调整申请、offline 下架申请四类';

-- ------------------------------------------------------------
-- 4.13 assistant_summon · 召唤记录
-- ------------------------------------------------------------
CREATE TABLE `assistant_summon` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增',
    `company_id`    BIGINT       NOT NULL COMMENT '公司 ID，多租户隔离字段',
    `assistant_id`     BIGINT       NOT NULL COMMENT '被召唤的助理 ID，外键指向 assistant.id',
    `user_id`       BIGINT       NOT NULL COMMENT '召唤用户 ID',
    `session_id`    VARCHAR(64)  NOT NULL COMMENT '会话 ID，每次召唤生成一个独立会话',
    `session_title` VARCHAR(128) NULL COMMENT '会话标题快照，用于召唤记录列表展示',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '召唤时间',
    PRIMARY KEY (`id`),
    KEY `idx_summon_user` (`company_id`, `user_id`, `created_at` DESC),
    CONSTRAINT `fk_summon_assistant` FOREIGN KEY (`assistant_id`) REFERENCES `assistant` (`id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '召唤记录；召唤不修改助理配置，每次召唤生成独立会话';

-- ------------------------------------------------------------
-- 4.14 sys_audit_log · 操作审计日志（按月分区）
-- ------------------------------------------------------------
CREATE TABLE `sys_audit_log` (
    `id`            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键 ID，自增（与 created_at 组成联合主键）',
    `company_id`    BIGINT       NOT NULL COMMENT '公司 ID，多租户隔离字段',
    `operator_id`   BIGINT       NULL COMMENT '操作人用户 ID；系统自动任务为空',
    `operator_name` VARCHAR(64)  NULL COMMENT '操作人姓名快照；系统自动任务为空',
    `action`        VARCHAR(48)  NOT NULL COMMENT '操作动作编码，如 assistant_create / share_submit / grant_remove / approval_approve',
    `object_type`   VARCHAR(32)  NOT NULL COMMENT '操作对象类型，如 assistant / approval / grant',
    `object_id`     VARCHAR(64)  NULL COMMENT '操作对象 ID，与 object_type 组合定位对象',
    `before_value`  JSON         NULL COMMENT '变更前授权范围等结构化快照',
    `after_value`   JSON         NULL COMMENT '变更后授权范围等结构化快照',
    `client_ip`     VARCHAR(64)  NULL COMMENT '客户端 IP 地址，含 IPv6',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间，RANGE COLUMNS 分区键',
    PRIMARY KEY (`id`, `created_at`),
    KEY `idx_audit_object` (`object_type`, `object_id`, `created_at` DESC),
    KEY `idx_audit_operator` (`company_id`, `operator_id`, `created_at` DESC)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci
  COMMENT = '操作审计，覆盖助理创建/编辑/删除/召唤、共享提交/重提、移除/重新订阅、审批通过与拒绝；按月分区，保留 ≥12 个月'
  PARTITION BY RANGE COLUMNS (`created_at`) (
    PARTITION `p2026q4` VALUES LESS THAN ('2027-01-01'),
    PARTITION `p_max`   VALUES LESS THAN (MAXVALUE)
  );

-- ============================================================
-- 7. 初始化数据
-- ============================================================
INSERT INTO `assistant_category` (`company_id`, `name`, `sort_no`, `is_builtin`) VALUES
    (1, '协同办公', 10, 1),
    (1, '人资',     20, 1),
    (1, '智慧云仓', 30, 1),
    (1, '环安',     40, 1),
    (1, '经营管理', 50, 1);

-- 平台内置助理：source='platform'，owner_user_id 为空，share_status='approved'
INSERT INTO `assistant`
    (`company_id`, `name`, `avatar_type`, `avatar_char`, `avatar_color`, `description`, `category_id`,
     `source`, `owner_user_id`, `owner_name`, `owner_dept_name`, `prompt`, `share_status`, `has_shared`,
     `version`, `authorized_count`, `created_by`)
VALUES
    (1, '智能会议助理', 'char', '会', '#5E9DF5',
     '会议前生成议程，会议中记录要点，会议后输出纪要与待办，并同步到日程。',
     (SELECT `id` FROM `assistant_category` WHERE `name` = '协同办公' AND `company_id` = 1),
     'platform', NULL, NULL, NULL,
     '你是九牧集团智能会议助理，负责输出会议议程、纪要与待办。', 'approved', 1, 'V1.6.0', 0, 0),
    (1, 'AI 陪练助理', 'char', '练', '#04D999',
     '按岗位场景模拟客户或员工对话，实时评分并给出改进建议。',
     (SELECT `id` FROM `assistant_category` WHERE `name` = '人资' AND `company_id` = 1),
     'platform', NULL, NULL, NULL,
     '你是九牧集团 AI 陪练助理，负责场景模拟对话与评分建议。', 'approved', 1, 'V2.1.0', 0, 0),
    (1, 'AI 面试助理', 'char', '面', '#FF813B',
     '按岗位模板发起结构化面试，输出候选人能力画像与面评报告。',
     (SELECT `id` FROM `assistant_category` WHERE `name` = '人资' AND `company_id` = 1),
     'platform', NULL, NULL, NULL,
     '你是九牧集团 AI 面试助理，负责结构化面试与面评报告。', 'approved', 1, 'V1.9.0', 0, 0),
    (1, '人效分析助理', 'char', '效', '#3685F2',
     '汇总人力投入与产出数据，输出部门人效对比与改善建议。',
     (SELECT `id` FROM `assistant_category` WHERE `name` = '人资' AND `company_id` = 1),
     'platform', NULL, NULL, NULL,
     '你是九牧集团人效分析助理，负责人效对比与改善建议。', 'approved', 1, 'V1.3.0', 0, 0),
    (1, '智慧云仓助理', 'char', '仓', '#2468F2',
     '解答库存、盘点与调度规则，支持按库区维度汇总异常。',
     (SELECT `id` FROM `assistant_category` WHERE `name` = '智慧云仓' AND `company_id` = 1),
     'platform', NULL, NULL, NULL,
     '你是九牧集团智慧云仓助理，负责库存、盘点与调度规则答疑。', 'approved', 1, 'V1.2.0', 0, 0),
    (1, '环安合规助理', 'char', '安', '#00B780',
     '检索环安法规与内部标准，输出合规检查项与整改建议。',
     (SELECT `id` FROM `assistant_category` WHERE `name` = '环安' AND `company_id` = 1),
     'platform', NULL, NULL, NULL,
     '你是九牧集团环安合规助理，负责法规检索与合规检查建议。', 'approved', 1, 'V1.1.0', 0, 0);

-- 平台内置助理的自定义标签（与原型 Mock 数据一致）
INSERT INTO `assistant_tag` (`assistant_id`, `name`, `sort_no`)
SELECT e.`id`, t.`name`, t.`sort_no`
FROM `assistant` e
JOIN (
    SELECT '智能会议助理' AS `assistant_name`, '会议' AS `name`, 10 AS `sort_no`
    UNION ALL SELECT '智能会议助理', '纪要', 20
    UNION ALL SELECT 'AI 陪练助理', '培训', 10
    UNION ALL SELECT 'AI 陪练助理', '陪练', 20
    UNION ALL SELECT 'AI 面试助理', '面试', 10
    UNION ALL SELECT 'AI 面试助理', '评估', 20
    UNION ALL SELECT '人效分析助理', '人效', 10
    UNION ALL SELECT '人效分析助理', '分析', 20
    UNION ALL SELECT '智慧云仓助理', '仓储', 10
    UNION ALL SELECT '智慧云仓助理', '调度', 20
    UNION ALL SELECT '环安合规助理', '环安', 10
    UNION ALL SELECT '环安合规助理', '合规', 20
) t ON e.`name` = t.`assistant_name` AND e.`company_id` = 1 AND e.`deleted_at` IS NULL;
