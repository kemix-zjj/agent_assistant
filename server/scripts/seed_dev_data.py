"""联调辅助：造一批待审批数据，便于前端联调时看到审批中心。

用法：python scripts/seed_dev_data.py
生成 2 个自建助理并提交共享（一条 share 申请 + 一条被拒后重提的场景）。
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

ASSISTANTS = [
    {
        "name": "车间排班助理",
        "avatarChar": "排",
        "avatarColor": "#5E9DF5",
        "categoryId": 1,
        "description": "按产线节拍与人员技能矩阵生成排班建议，输出缺口岗位与调休方案。",
        "tags": ["排班", "考勤"],
        "prompt": "你是生产车间排班助理，负责生成排班建议与人员缺口分析。",
        "skillIds": ["s4", "s9"],
        "mcpIds": ["m3"],
        "knowledgeBaseIds": ["k3"],
        "quickQuestions": ["本周末排班怎么安排？", "产线缺人时怎么调休？"],
        "scope": {"scopeMode": "RANGE", "orgs": ["O11"], "roles": [], "positions": [], "users": []},
        "note": "首次申请共享，覆盖招聘组",
    },
    {
        "name": "仓储盘点助理",
        "avatarChar": "盘",
        "avatarColor": "#2468F2",
        "categoryId": 3,
        "description": "指导盘点作业流程，解释差异处理规则，输出盘点复盘要点与改进项。",
        "tags": ["盘点", "仓储"],
        "prompt": "你是智慧云仓仓储盘点助理，负责指导盘点作业与差异处理。",
        "skillIds": ["s5"],
        "mcpIds": ["m5"],
        "knowledgeBaseIds": ["k4"],
        "quickQuestions": ["盘点差异如何处理？"],
        "scope": {
            "scopeMode": "RANGE",
            "orgs": ["O12"],
            "roles": [],
            "positions": [],
            "users": ["u6"],
        },
        "note": "覆盖仓储运营部与物流调度部",
    },
]


def main() -> int:
    with httpx.Client(timeout=15) as c:
        for item in ASSISTANTS:
            payload = {
                "name": item["name"],
                "avatarType": "char",
                "avatarChar": item["avatarChar"],
                "avatarUrl": None,
                "avatarColor": item["avatarColor"],
                "description": item["description"],
                "tags": item["tags"],
                "categoryId": item["categoryId"],
                "prompt": item["prompt"],
                "skillIds": item["skillIds"],
                "mcpIds": item["mcpIds"],
                "knowledgeBaseIds": item["knowledgeBaseIds"],
                "quickQuestions": item["quickQuestions"],
            }
            created = c.post(f"{BASE}/assistants", headers=OWNER, json=payload)
            if created.status_code != 201:
                print(f"创建失败 {item['name']}: {created.status_code} {created.text}")
                continue
            aid = created.json()["data"]["assistantId"]

            submitted = c.post(
                f"{BASE}/shares",
                headers=OWNER,
                json={
                    "assistantIds": [aid],
                    "scope": item["scope"],
                    "changeNote": item["note"],
                },
            )
            if submitted.status_code != 201:
                print(f"提交共享失败 {item['name']}: {submitted.status_code} {submitted.text}")
                continue
            approval_id = submitted.json()["data"]["approvalIds"][0]
            print(f"已创建 {item['name']}（id={aid}），审批单 {approval_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
