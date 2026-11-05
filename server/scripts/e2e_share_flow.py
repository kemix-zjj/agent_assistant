"""端到端验证：共享提交与四维范围展开。

用法：python scripts/e2e_share_flow.py
结束后清理本次创建的全部数据。
"""

import sys
from pathlib import Path
from urllib.parse import quote

import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def h(user_id: str, name: str, dept: str | None = None) -> dict:
    headers = {"X-User-Id": user_id, "X-User-Name": quote(name)}
    if dept:
        headers["X-User-Dept"] = quote(dept)
    return headers


OWNER = h("1001", "王晓明", "人力资源部 · 招聘组")
ADMIN = h("9001", "王建国", "经营管理中心")
GRANTEE = h("2001", "李静")


def scope(**overrides) -> dict:
    data = {"scopeMode": "RANGE", "orgs": [], "roles": [], "positions": [], "users": []}
    data.update(overrides)
    return data


PAYLOAD = {
    "name": "端到端验证助理",
    "avatarType": "char",
    "avatarChar": "验",
    "avatarUrl": None,
    "avatarColor": "#3685F2",
    "description": "端到端验证共享提交与四维范围展开，覆盖完整审批前链路。",
    "tags": ["验证"],
    "categoryId": 2,
    "prompt": "你是端到端验证助理。",
    "skillIds": [],
    "mcpIds": [],
    "knowledgeBaseIds": [],
    "quickQuestions": [],
}


def show(label: str, value: object) -> None:
    print(f"{label}: {value}")


def main() -> int:
    with httpx.Client(timeout=15) as c:
        # 1. 主数据
        tree = c.get(f"{BASE}/scopes/org-tree", headers=OWNER).json()["data"]["tree"]
        show("组织树根", f"{tree[0]['name']}（{len(tree[0]['children'])} 个二级部门）")

        roles = c.get(f"{BASE}/scopes/roles", headers=OWNER).json()["data"]["list"]
        show("角色", [r["name"] for r in roles])

        users = c.get(
            f"{BASE}/scopes/users", headers=OWNER, params={"orgIds": "O11"}
        ).json()["data"]
        show("O11 覆盖人员", f"{[u['name'] for u in users['list']]}（共 {users['total']} 人）")

        # 2. 四维展开
        expand = c.post(
            f"{BASE}/scopes/expand",
            headers=OWNER,
            json=scope(orgs=["O11"], positions=["p2"], users=["u1"]),
        ).json()["data"]
        show(
            "展开结果",
            f"grantTotal={expand['grantTotal']} 人员={[(u['name'], u['sources']) for u in expand['users']]}",
        )

        over = c.post(
            f"{BASE}/scopes/expand",
            headers=OWNER,
            json=scope(users=[f"u{i}" for i in range(201)]),
        )
        show("超限校验", f"HTTP={over.status_code} code={over.json()['code']}")

        # 3. 创建助理并提交共享
        created = c.post(f"{BASE}/assistants", headers=OWNER, json=PAYLOAD).json()["data"]
        aid = created["assistantId"]
        show("创建助理", f"id={aid} 状态={created['shareStatus']}")

        submitted = c.post(
            f"{BASE}/shares",
            headers=OWNER,
            json={
                "assistantIds": [aid],
                "scope": scope(orgs=["O11"], users=["u5"]),
                "changeNote": "首次申请共享，覆盖人力资源部与周涛",
            },
        )
        sub = submitted.json()["data"]
        show(
            "提交共享",
            f"HTTP={submitted.status_code} 批次={sub['batchNo']} 审批单={sub['approvalIds']} 数量={sub['submittedCount']}",
        )

        detail = c.get(f"{BASE}/assistants/{aid}", headers=OWNER).json()["data"]
        show("助理状态", f"{detail['shareStatus']}｜版本记录首条={detail['versionHistory'][0]['action']}")
        show(
            "回显范围",
            f"模式={detail['shareScope']['scopeMode']} 合计={detail['shareScope']['grantTotal']} 人 摘要={detail['shareScope']['summary']}",
        )

        again = c.post(
            f"{BASE}/shares",
            headers=OWNER,
            json={"assistantIds": [aid], "scope": scope(users=["u1"])},
        )
        show("重复提交", f"HTTP={again.status_code} code={again.json()['code']}")

        readonly = c.get(f"{BASE}/assistants/{aid}/share-scope", headers=GRANTEE).json()["data"]
        show("被授权方视角", f"editableBy={readonly['editableBy']} editable={readonly['editable']}")

        # 4. 管理员直改范围（先造一个已共享的助理需审批通过，这里用另一个助理验证分支 B）
        second = c.post(
            f"{BASE}/assistants",
            headers=OWNER,
            json={**PAYLOAD, "name": "端到端验证助理二"},
        ).json()["data"]
        aid2 = second["assistantId"]

        direct = c.put(
            f"{BASE}/assistants/{aid2}/share-scope",
            headers=ADMIN,
            json={"scope": scope(orgs=["O11"]), "changeNote": "管理员直接配置范围"},
        ).json()["data"]
        show("管理员直改", f"applied={direct['applied']} 合计={direct['scope']['grantTotal']} 人")

        shared = c.get(
            f"{BASE}/assistants", headers=GRANTEE, params={"scope": "shared", "pageSize": 50}
        ).json()["data"]
        hit = [x for x in shared["list"] if x["assistantId"] == aid2]
        show(
            "被授权方共享助理",
            f"命中={bool(hit)} actions={hit[0]['actions'] if hit else None}",
        )

        # 5. 清理
        for x in (aid, aid2):
            c.delete(f"{BASE}/assistants/{x}", headers=OWNER)
        show("清理", "已删除两个验证助理")

    print("\n全部步骤完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
