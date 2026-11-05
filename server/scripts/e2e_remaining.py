"""端到端验证：剩余 7 个接口。

用法：python scripts/e2e_remaining.py
结束后清理本次创建的全部数据。
"""

import sys
from pathlib import Path
from urllib.parse import quote

import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def h(user_id: str, name: str) -> dict:
    return {"X-User-Id": user_id, "X-User-Name": quote(name)}


OWNER = h("1001", "王晓明")
ADMIN = h("9001", "王建国")
GRANTEE = h("2001", "李静")


def scope(**overrides) -> dict:
    data = {"scopeMode": "RANGE", "orgs": [], "roles": [], "positions": [], "users": []}
    data.update(overrides)
    return data


PAYLOAD = {
    "name": "端到端验证助理",
    "avatarType": "char",
    "avatarChar": "全",
    "avatarColor": "#3685F2",
    "description": "端到端验证剩余接口，覆盖资源、召唤、订阅、AI 与头像预签名。",
    "tags": ["验证"],
    "categoryId": 2,
    "prompt": "你是验证助理。",
    "skillIds": [],
    "mcpIds": [],
    "knowledgeBaseIds": [],
    "quickQuestions": ["怎么用？"],
}


def show(label: str, value: object) -> None:
    print(f"{label}: {value}")


def main() -> int:
    with httpx.Client(timeout=15) as c:
        # 1. 资源候选列表
        skills = c.get(f"{BASE}/resources/skills", headers=OWNER).json()["data"]["list"]
        show("SKILL 列表", f"{len(skills)} 项，首个={skills[0]['name']}（{skills[0]['desc'][:12]}…）")

        hit = c.get(f"{BASE}/resources/skills", headers=OWNER, params={"keyword": "简历"})
        show("SKILL 搜索", f"命中 {len(hit.json()['data']['list'])} 项")

        mcps = c.get(f"{BASE}/resources/mcps", headers=OWNER).json()["data"]["list"]
        show("MCP 列表", f"{len(mcps)} 项，首个={mcps[0]['name']}（{mcps[0]['type']}）")

        kbs = c.get(f"{BASE}/resources/knowledge-bases", headers=OWNER).json()["data"]["list"]
        show(
            "知识库列表",
            f"{len(kbs)} 项，首个={kbs[0]['name']}（{kbs[0]['documentCount']} 篇 / {len(kbs[0]['files'])} 个文件）",
        )

        # 2. 创建助理并召唤
        created = c.post(f"{BASE}/assistants", headers=OWNER, json=PAYLOAD).json()["data"]
        aid = created["assistantId"]
        summon = c.post(f"{BASE}/assistants/{aid}/summon", headers=OWNER, json={"source": "card"})
        s = summon.json()["data"]
        show("召唤", f"HTTP={summon.status_code} 会话={s['sessionId']} 标题={s['sessionTitle']}")
        show("召唤返回", f"头像={s['assistantAvatar']['char']} 快速问题={s['quickQuestions']}")

        # 3. 提交并审批通过，然后订阅移除/重订
        sub = c.post(
            f"{BASE}/shares",
            headers=OWNER,
            json={"assistantIds": [aid], "scope": scope(users=["u1"])},
        ).json()["data"]
        c.post(f"{BASE}/approvals/{sub['approvalIds'][0]}/approve", headers=ADMIN, json={})

        removed = c.put(
            f"{BASE}/assistants/{aid}/subscription", headers=GRANTEE, json={"action": "remove"}
        ).json()["data"]
        show("移除订阅", removed)

        blocked = c.post(f"{BASE}/assistants/{aid}/summon", headers=GRANTEE, json={})
        show("移除后召唤", f"HTTP={blocked.status_code} code={blocked.json()['code']}")

        back = c.put(
            f"{BASE}/assistants/{aid}/subscription",
            headers=GRANTEE,
            json={"action": "resubscribe"},
        ).json()["data"]
        show("重新订阅", back)

        shared = c.get(
            f"{BASE}/assistants", headers=GRANTEE, params={"scope": "shared", "pageSize": 50}
        ).json()["data"]["list"]
        hit_card = next((x for x in shared if x["assistantId"] == aid), None)
        show("共享列表", f"命中={bool(hit_card)} actions={hit_card['actions'] if hit_card else None}")

        # 4. AI 生成
        desc = c.post(
            f"{BASE}/ai/generate",
            headers=OWNER,
            json={
                "field": "description",
                "name": "招聘面试助理",
                "categoryName": "人资",
                "currentValue": None,
                "mode": "auto",
            },
        ).json()["data"]
        show("AI 生成描述", f"mode={desc['mode']} 长度={len(desc['value'])} 命中上限={desc['hitLimit']}")

        tags = c.post(
            f"{BASE}/ai/generate",
            headers=OWNER,
            json={"field": "tags", "name": "考勤答疑助理", "categoryName": "人资"},
        ).json()["data"]
        show("AI 生成标签", tags["value"])

        polish = c.post(
            f"{BASE}/ai/generate",
            headers=OWNER,
            json={"field": "description", "name": "考勤助理", "currentValue": "解答考勤规则。"},
        ).json()["data"]
        show("AI 润色描述", f"mode={polish['mode']} 值={polish['value'][:26]}…")

        qq = c.post(
            f"{BASE}/ai/generate", headers=OWNER, json={"field": "quickQuestions", "name": "考勤助理"}
        ).json()["data"]
        show("AI 生成快速问题", f"{len(qq['value'])} 条")

        # 5. 头像预签名
        presign = c.post(
            f"{BASE}/common/avatar-presign",
            headers=OWNER,
            json={"fileName": "avatar.png", "contentType": "image/png", "fileSize": 1048576},
        ).json()["data"]
        show("头像预签名", f"key={presign['objectKey']} 有效期={presign['expiresIn']}s")

        bad = c.post(
            f"{BASE}/common/avatar-presign",
            headers=OWNER,
            json={"fileName": "a.pdf", "contentType": "application/pdf", "fileSize": 1024},
        )
        show("非图片拦截", f"HTTP={bad.status_code} code={bad.json()['code']}")

        # 6. 清理
        c.delete(f"{BASE}/assistants/{aid}", headers=OWNER)
        show("清理", "已删除验证助理")

    print("\n全部步骤完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
