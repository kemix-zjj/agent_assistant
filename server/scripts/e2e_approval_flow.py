"""端到端验证：审批中心完整链路。

用法：python scripts/e2e_approval_flow.py
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


def scope(**overrides) -> dict:
    data = {"scopeMode": "RANGE", "orgs": [], "roles": [], "positions": [], "users": []}
    data.update(overrides)
    return data


PAYLOAD = {
    "name": "端到端验证助理",
    "avatarType": "char",
    "avatarChar": "审",
    "avatarColor": "#3685F2",
    "description": "端到端验证审批中心链路，覆盖提交、调整、通过与拒绝分支。",
    "tags": ["验证"],
    "categoryId": 2,
    "prompt": "你是审批验证助理。",
    "skillIds": ["s4"],
    "mcpIds": ["m3"],
    "knowledgeBaseIds": ["k3"],
    "quickQuestions": [],
}


def show(label: str, value: object) -> None:
    print(f"{label}: {value}")


def main() -> int:
    created: list[int] = []
    with httpx.Client(timeout=15) as c:
        # 1. 造两条待审批：一条走通过，一条走拒绝
        for suffix in ("通过", "拒绝"):
            data = c.post(
                f"{BASE}/assistants",
                headers=OWNER,
                json={**PAYLOAD, "name": f"端到端验证助理{suffix}"},
            ).json()["data"]
            created.append(data["assistantId"])
            c.post(
                f"{BASE}/shares",
                headers=OWNER,
                json={
                    "assistantIds": [data["assistantId"]],
                    "scope": scope(orgs=["O11"]),
                    "changeNote": f"{suffix}分支验证",
                },
            )

        # 2. 列表与角标
        pending = c.get(f"{BASE}/approvals", headers=ADMIN).json()["data"]
        show("待审批列表", f"total={pending['total']}")
        card = next(x for x in pending["list"] if x["assistantId"] == created[0])
        show(
            "列表项",
            f"{card['approvalTypeName']}｜{card['assistantName']}｜{card['submitterName']}｜{card['scopeSummary']}",
        )
        count = c.get(f"{BASE}/approvals/pending-count", headers=ADMIN).json()["data"]
        show("角标", count)

        # 3. 审批前调整范围
        adjust = c.put(
            f"{BASE}/approvals/{card['approvalId']}/scope",
            headers=ADMIN,
            json={"scope": scope(users=["u1", "u3"])},
        ).json()["data"]
        show(
            "调整范围",
            f"已调整={adjust['scopeAdjusted']} 合计={adjust['scope']['grantTotal']} 人｜"
            f"新增{adjust['scopeDiff']['addedCount']} 移除{adjust['scopeDiff']['removedCount']}",
        )
        detail = c.get(f"{BASE}/approvals/{card['approvalId']}", headers=ADMIN).json()["data"]
        show(
            "详情",
            f"提示词长度={len(detail['assistant']['prompt'])} scopeAdjusted={detail['scopeAdjusted']} "
            f"configChanged={detail['assistantConfigChanged']}",
        )

        # 4. 审批通过（用调整后的范围）
        approved = c.post(
            f"{BASE}/approvals/{card['approvalId']}/approve",
            headers=ADMIN,
            json={"comment": "同意共享"},
        ).json()["data"]
        show("审批通过", f"状态={approved['status']} 授权={approved['grantTotal']} 人")

        again = c.post(
            f"{BASE}/approvals/{card['approvalId']}/approve", headers=ADMIN, json={}
        )
        show("重复通过", f"HTTP={again.status_code} 状态={again.json()['data']['status']}")

        # 5. 审批拒绝
        reject_card = next(
            x
            for x in c.get(f"{BASE}/approvals", headers=ADMIN).json()["data"]["list"]
            if x["assistantId"] == created[1]
        )
        rejected = c.post(
            f"{BASE}/approvals/{reject_card['approvalId']}/reject",
            headers=ADMIN,
            json={"rejectReason": "授权范围包含外协单位组织节点，请收敛后重新提交。"},
        ).json()["data"]
        show("审批拒绝", f"状态={rejected['status']} 原因={rejected['rejectReason'][:16]}…")

        # 6. 被授权方视角
        for login_id, name in (("2001", "李静"), ("2003", "陈志远")):
            shared = c.get(
                f"{BASE}/assistants",
                headers=h(login_id, name),
                params={"scope": "shared", "pageSize": 50},
            ).json()["data"]
            hit = [x for x in shared["list"] if x["assistantId"] == created[0]]
            show(f"被授权方 {name}", f"命中={bool(hit)} actions={hit[0]['actions'] if hit else None}")

        # 7. 拒绝后重新提交
        resubmit = c.post(
            f"{BASE}/shares",
            headers=OWNER,
            json={"assistantIds": [created[1]], "scope": scope(users=["u2"])},
        )
        show("拒绝后重提", f"HTTP={resubmit.status_code}")
        detail2 = c.get(f"{BASE}/assistants/{created[1]}", headers=OWNER).json()["data"]
        show("重提后状态", f"{detail2['shareStatus']}｜拒绝原因为空={detail2['rejectReason'] if 'rejectReason' in detail2 else 'n/a'}")

        # 8. 清理
        for aid in created:
            c.delete(f"{BASE}/assistants/{aid}", headers=OWNER)
        show("清理", f"已删除 {len(created)} 个验证助理")

    print("\n全部步骤完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
