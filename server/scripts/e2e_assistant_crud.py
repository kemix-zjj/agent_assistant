"""端到端验证脚本：对运行中的服务走一遍助理 CRUD 全流程。

用法：python scripts/e2e_assistant_crud.py
结束后自动删除本次创建的助理，不在库中留下业务数据。
"""

import sys
from pathlib import Path
from urllib.parse import quote

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
HEADERS = {
    "X-User-Id": "1001",
    "X-User-Name": quote("王晓明"),
    "X-User-Dept": quote("人力资源部 · 招聘组"),
}

PAYLOAD = {
    "name": "端到端验证助理",
    "avatarType": "char",
    "avatarChar": "验",
    "avatarUrl": None,
    "avatarColor": "#3685F2",
    "description": "端到端验证用助理，覆盖创建、列表、详情、编辑、删除影响面与删除。",
    "tags": ["验证"],
    "categoryId": 2,
    "prompt": "你是端到端验证助理。",
    "skillIds": ["s1"],
    "mcpIds": ["m1"],
    "knowledgeBaseIds": ["k1"],
    "quickQuestions": ["怎么用？"],
}


def show(label: str, value: object) -> None:
    print(f"{label}: {value}")


def main() -> int:
    with httpx.Client(timeout=15) as client:
        created = client.post(f"{BASE}/assistants", headers=HEADERS, json=PAYLOAD)
        if created.status_code != 201:
            print("创建失败", created.status_code, created.text)
            return 1
        data = created.json()["data"]
        aid = data["assistantId"]
        show("创建", f"id={aid} 状态={data['shareStatus']} 版本={data['version']} 分类={data['categoryName']}")
        show("能力组成", f"skills={[s['name'] for s in data['skills']]} mcps={[m['name'] for m in data['mcps']]}")

        listed = client.get(
            f"{BASE}/assistants", headers=HEADERS, params={"scope": "mine", "pageSize": 50}
        ).json()["data"]
        show("我的助理列表", f"total={listed['total']} 命中={aid in [c['assistantId'] for c in listed['list']]}")
        card = next(c for c in listed["list"] if c["assistantId"] == aid)
        show("卡片 actions", card["actions"])
        show("卡片截断描述", card["descriptionTruncated"][:30] + "…")

        detail = client.get(f"{BASE}/assistants/{aid}", headers=HEADERS).json()["data"]
        show("详情", f"prompt={detail['prompt']} 版本记录={[(h['version'], h['action']) for h in detail['versionHistory']]}")

        updated = client.put(f"{BASE}/assistants/{aid}", headers=HEADERS, json={**PAYLOAD, "tags": ["验证", "编辑"]})
        show("编辑", f"HTTP={updated.status_code} 新版本={updated.json()['data']['version']} 影响授权={updated.headers.get('X-Affected-Grant-Count')}")

        impact = client.get(f"{BASE}/assistants/{aid}/delete-impact", headers=HEADERS).json()["data"]
        show("删除影响面", impact)

        deleted = client.delete(f"{BASE}/assistants/{aid}", headers=HEADERS)
        show("删除", f"HTTP={deleted.status_code} body={deleted.json()['data']}")

        gone = client.get(f"{BASE}/assistants/{aid}", headers=HEADERS)
        show("删除后查询", f"HTTP={gone.status_code} code={gone.json()['code']}")

    print("\n全部步骤完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
