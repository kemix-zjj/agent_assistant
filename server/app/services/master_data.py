"""主数据：组织树 / 角色 / 岗位 / 人员（四维范围选择的来源）。

对应 docs/02 Q-08：主数据不落本地库，实时调主数据服务；`share_scope_item`
仅保存 ID 与名称快照。接入真实主数据平台时，替换本模块的查询函数即可。

本期为演示数据，与前端原型保持一致。
"""

from dataclasses import dataclass, field

# ============================ 组织树 ============================


@dataclass(frozen=True)
class OrgNode:
    id: str
    name: str
    level: int
    children: tuple["OrgNode", ...] = ()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "children": [child.to_dict() for child in self.children],
        }


ORG_TREE: tuple[OrgNode, ...] = (
    OrgNode(
        "O1",
        "九牧集团有限公司",
        1,
        (
            OrgNode(
                "O11",
                "人力资源部",
                2,
                (
                    OrgNode("O111", "招聘组", 3),
                    OrgNode("O112", "薪酬绩效组", 3),
                ),
            ),
            OrgNode(
                "O12",
                "智慧云仓事业部",
                2,
                (
                    OrgNode("O121", "仓储运营部", 3),
                    OrgNode("O122", "物流调度部", 3),
                ),
            ),
            OrgNode("O13", "环安管理部", 2),
            OrgNode(
                "O14",
                "经营管理中心",
                2,
                (OrgNode("O141", "报价管理组", 3),),
            ),
        ),
    ),
)


def _flatten(nodes: tuple[OrgNode, ...]) -> dict[str, OrgNode]:
    result: dict[str, OrgNode] = {}
    for node in nodes:
        result[node.id] = node
        result.update(_flatten(node.children))
    return result


_ORG_INDEX = _flatten(ORG_TREE)


def org_name(org_id: str) -> str:
    node = _ORG_INDEX.get(org_id)
    return node.name if node else org_id


def org_ids_under(org_id: str) -> list[str]:
    """组织节点自身 + 全部下级节点 ID。"""
    node = _ORG_INDEX.get(org_id)
    if node is None:
        return []

    collected: list[str] = []

    def walk(current: OrgNode) -> None:
        collected.append(current.id)
        for child in current.children:
            walk(child)

    walk(node)
    return collected


def search_org_tree(keyword: str | None) -> list[dict]:
    """按关键词过滤，命中节点保留其祖先链，保证树结构完整。"""
    if not keyword:
        return [node.to_dict() for node in ORG_TREE]

    def filter_node(node: OrgNode) -> dict | None:
        children = [c for c in (filter_node(child) for child in node.children) if c]
        if keyword in node.name or children:
            return {
                "id": node.id,
                "name": node.name,
                "level": node.level,
                "children": children,
            }
        return None

    return [item for item in (filter_node(node) for node in ORG_TREE) if item]


# ============================ 角色 / 岗位 ============================


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    desc: str


ROLES: tuple[Role, ...] = (
    Role("r1", "招聘专员", "负责简历筛选与面试安排"),
    Role("r2", "薪酬专员", "负责薪资核算与个税申报"),
    Role("r3", "仓储主管", "负责库区作业与盘点管理"),
    Role("r4", "环安工程师", "负责隐患排查与合规检查"),
)

POSITIONS: tuple[Role, ...] = (
    Role("p1", "专员", "专业序列"),
    Role("p2", "主管", "基层管理"),
    Role("p3", "经理", "中层管理"),
)

_ROLE_INDEX = {item.id: item for item in ROLES}
_POSITION_INDEX = {item.id: item for item in POSITIONS}


def role_name(role_id: str) -> str:
    item = _ROLE_INDEX.get(role_id)
    return item.name if item else role_id


def position_name(position_id: str) -> str:
    item = _POSITION_INDEX.get(position_id)
    return item.name if item else position_id


# ============================ 人员 ============================


@dataclass(frozen=True)
class Employee:
    id: str
    name: str
    dept_name: str
    job_no: str
    org_id: str
    roles: tuple[str, ...] = ()
    position_id: str = ""
    # 登录账号 ID（网关下发），用于把当前登录用户映射到主数据人员
    login_id: int = 0
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "deptName": self.dept_name,
            "jobNo": self.job_no,
        }


EMPLOYEES: tuple[Employee, ...] = (
    Employee("u1", "李静", "人力资源部 · 招聘组", "E0231", "O111", ("r1",), "p1", 2001),
    Employee("u2", "林晓", "人力资源部 · 薪酬绩效组", "E0187", "O112", ("r2",), "p1", 2002),
    Employee("u3", "陈志远", "智慧云仓事业部 · 仓储运营部", "E0342", "O121", ("r3",), "p2", 2003),
    Employee("u4", "赵敏", "环安管理部", "E0092", "O13", ("r4",), "p1", 2004),
    Employee("u5", "周涛", "经营管理中心 · 报价管理组", "E0512", "O141", (), "p3", 2005),
    Employee("u6", "吴磊", "智慧云仓事业部 · 物流调度部", "E0288", "O122", (), "p1", 2006),
)

_EMPLOYEE_INDEX = {item.id: item for item in EMPLOYEES}
_LOGIN_INDEX = {item.login_id: item for item in EMPLOYEES}


def employee(employee_id: str) -> Employee | None:
    return _EMPLOYEE_INDEX.get(employee_id)


def employee_id_for_login(login_id: int) -> str | None:
    """登录账号 ID → 主数据人员 ID；无对应人员返回 None（无共享助理可见）。"""
    item = _LOGIN_INDEX.get(login_id)
    return item.id if item else None


def headcount() -> int:
    """公司在职人数，用于 PUBLIC 模式的授权人数。"""
    return sum(1 for item in EMPLOYEES if item.active)


def search_employees(
    keyword: str | None = None, org_ids: list[str] | None = None
) -> list[Employee]:
    """按组织（含下级）与关键词（姓名 / 工号）过滤。"""
    result = list(EMPLOYEES)
    if org_ids:
        allowed: set[str] = set()
        for org_id in org_ids:
            allowed.update(org_ids_under(org_id))
        result = [item for item in result if item.org_id in allowed]
    if keyword:
        result = [
            item
            for item in result
            if keyword in item.name or keyword in item.job_no
        ]
    return result


# ============================ 上限 ============================

SCOPE_LIMITS: dict[str, int] = {"org": 50, "role": 50, "position": 50, "user": 200}


@dataclass
class ExpandedUser:
    """展开结果中的单个人，sources 标注覆盖来源。"""

    employee: Employee
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.employee.id,
            "name": self.employee.name,
            "deptName": self.employee.dept_name,
            "sources": self.sources,
        }
