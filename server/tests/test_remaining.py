"""剩余接口测试：资源列表、召唤、订阅、AI 生成、头像预签名。

对应 docs/03 §3.7 / §3.8 / §4.3~4.5 / §8.1 / §9.1。
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _h(user_id: str, name: str) -> dict[str, str]:
    from urllib.parse import quote

    return {"X-User-Id": user_id, "X-User-Name": quote(name)}


OWNER = _h("1001", "王晓明")
ADMIN = _h("9001", "王建国")
GRANTEE = _h("2001", "李静")


def _payload(name: str) -> dict:
    return {
        "name": name,
        "avatarType": "char",
        "avatarChar": "补",
        "avatarColor": "#3685F2",
        "description": "用于补全接口测试的助理，描述长度满足校验要求。",
        "tags": ["补全"],
        "categoryId": 2,
        "prompt": "你是补全测试助理。",
        "skillIds": [],
        "mcpIds": [],
        "knowledgeBaseIds": [],
        "quickQuestions": ["这个助理怎么用？"],
    }


def _scope(**overrides) -> dict:
    data = {"scopeMode": "RANGE", "orgs": [], "roles": [], "positions": [], "users": []}
    data.update(overrides)
    return data


def _create(name: str) -> int:
    resp = client.post("/api/v1/assistants", headers=OWNER, json=_payload(name))
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["assistantId"]


def _publish(aid: int, scope: dict | None = None) -> None:
    """提交共享并由管理员通过，使助理进入 approved 且有授权。"""
    submitted = client.post(
        "/api/v1/shares",
        headers=OWNER,
        json={"assistantIds": [aid], "scope": scope or _scope(users=["u1"])},
    )
    assert submitted.status_code == 201, submitted.text
    approval_id = submitted.json()["data"]["approvalIds"][0]
    approved = client.post(
        f"/api/v1/approvals/{approval_id}/approve", headers=ADMIN, json={}
    )
    assert approved.status_code == 200, approved.text


# ============================ 资源候选列表 ============================


def test_resource_skills_list() -> None:
    resp = client.get("/api/v1/resources/skills", headers=OWNER)
    assert resp.status_code == 200
    items = resp.json()["data"]["list"]
    assert len(items) == 10
    assert items[0]["id"] == "s1"
    assert items[0]["desc"]
    assert items[0]["market"] == "internal"


def test_resource_skills_keyword_filter() -> None:
    resp = client.get("/api/v1/resources/skills", headers=OWNER, params={"keyword": "简历"})
    items = resp.json()["data"]["list"]
    assert [i["name"] for i in items] == ["简历初筛"]


def test_resource_mcps_list() -> None:
    resp = client.get("/api/v1/resources/mcps", headers=OWNER)
    items = resp.json()["data"]["list"]
    assert len(items) == 8
    assert items[0]["type"] == "组织数据"
    assert any(i["market"] == "external" for i in items)


def test_resource_knowledge_bases_list() -> None:
    resp = client.get("/api/v1/resources/knowledge-bases", headers=OWNER)
    items = resp.json()["data"]["list"]
    assert len(items) == 6
    assert items[0]["documentCount"] == 128
    assert items[0]["files"]


def test_resource_keyword_too_long() -> None:
    resp = client.get(
        "/api/v1/resources/skills", headers=OWNER, params={"keyword": "长" * 51}
    )
    assert resp.status_code == 400
    assert resp.json()["data"]["field"] == "keyword"


def test_resource_requires_login() -> None:
    resp = client.get("/api/v1/resources/skills")
    assert resp.status_code == 401


# ============================ 召唤 ============================


def test_summon_own_assistant() -> None:
    aid = _create("补全测试助理召唤")
    try:
        resp = client.post(
            f"/api/v1/assistants/{aid}/summon", headers=OWNER, json={"source": "card"}
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["sessionId"].startswith("S")
        assert data["sessionTitle"] == "召唤 补全测试助理召唤"
        assert data["assistantId"] == aid
        assert data["AssistantAvatar"]["char"] == "补"
        assert data["quickQuestions"] == ["这个助理怎么用？"]
        assert data["createdAt"]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_summon_platform_assistant_always_available() -> None:
    """平台预置助理对任何登录用户可用（source=platform 恒可用）。"""
    resp = client.post(
        "/api/v1/assistants/1/summon", headers=_h("3001", "任意员工"), json={}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["assistantId"] == 1


def test_summon_shared_assistant_requires_subscription() -> None:
    aid = _create("补全测试助理共享召唤")
    try:
        _publish(aid)
        # 已订阅可用
        ok_resp = client.post(
            f"/api/v1/assistants/{aid}/summon", headers=GRANTEE, json={}
        )
        assert ok_resp.status_code == 200

        # 移除后不可召唤
        client.put(
            f"/api/v1/assistants/{aid}/subscription",
            headers=GRANTEE,
            json={"action": "remove"},
        )
        blocked = client.post(
            f"/api/v1/assistants/{aid}/summon", headers=GRANTEE, json={}
        )
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "ASSISTANT_NOT_AVAILABLE"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_summon_forbidden_for_unrelated_user() -> None:
    aid = _create("补全测试助理无权召唤")
    try:
        resp = client.post(
            f"/api/v1/assistants/{aid}/summon", headers=_h("3002", "无关用户"), json={}
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "NO_PERMISSION"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_summon_writes_record() -> None:
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.system import AssistantSummon

    aid = _create("补全测试助理召唤记录")
    try:
        session_id = client.post(
            f"/api/v1/assistants/{aid}/summon", headers=OWNER, json={}
        ).json()["data"]["sessionId"]

        db = SessionLocal()
        try:
            row = db.scalar(
                select(AssistantSummon).where(AssistantSummon.session_id == session_id)
            )
            assert row is not None
            assert row.assistant_id == aid
            assert row.user_id == 1001
        finally:
            db.close()
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_summon_not_found() -> None:
    resp = client.post("/api/v1/assistants/999999/summon", headers=OWNER, json={})
    assert resp.status_code == 404


# ============================ 订阅 ============================


def test_subscription_remove_and_resubscribe() -> None:
    aid = _create("补全测试助理订阅")
    try:
        _publish(aid)

        removed = client.put(
            f"/api/v1/assistants/{aid}/subscription",
            headers=GRANTEE,
            json={"action": "remove"},
        )
        assert removed.status_code == 200, removed.text
        assert removed.json()["data"]["subscribeStatus"] == "removed"

        # 已移除：卡片 actions 变为 resubscribe
        listed = client.get(
            "/api/v1/assistants",
            headers=GRANTEE,
            params={"scope": "shared", "subscribeFilter": "removed"},
        ).json()["data"]["list"]
        hit = next(c for c in listed if c["assistantId"] == aid)
        assert hit["actions"] == ["resubscribe"]

        back = client.put(
            f"/api/v1/assistants/{aid}/subscription",
            headers=GRANTEE,
            json={"action": "resubscribe"},
        )
        assert back.json()["data"]["subscribeStatus"] == "subscribed"

        subscribed = client.get(
            "/api/v1/assistants",
            headers=GRANTEE,
            params={"scope": "shared", "subscribeFilter": "subscribed", "pageSize": 50},
        ).json()["data"]["list"]
        assert aid in [c["assistantId"] for c in subscribed]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_subscription_does_not_affect_owner_status() -> None:
    """移除订阅不触碰 grant_status 与创建人侧 share_status（REQ-LIB-REMOVE-007）。"""
    aid = _create("补全测试助理订阅隔离")
    try:
        _publish(aid)
        client.put(
            f"/api/v1/assistants/{aid}/subscription",
            headers=GRANTEE,
            json={"action": "remove"},
        )
        owner_view = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert owner_view["shareStatus"] == "approved"

        # 创建人侧仍显示已共享，授权人数不变
        mine = client.get(
            "/api/v1/assistants", headers=OWNER, params={"scope": "mine", "pageSize": 50}
        ).json()["data"]["list"]
        hit = next(c for c in mine if c["assistantId"] == aid)
        assert hit["shareStatus"] == "approved"
        assert "shareScope" in hit["actions"]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_subscription_requires_valid_grant() -> None:
    aid = _create("补全测试助理无授权")
    try:
        resp = client.put(
            f"/api/v1/assistants/{aid}/subscription",
            headers=GRANTEE,
            json={"action": "remove"},
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == "GRANT_INVALID"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_subscription_after_grant_invalidated() -> None:
    """范围收紧导致授权失效后，重新订阅应报 GRANT_INVALID。"""
    aid = _create("补全测试助理授权失效")
    try:
        _publish(aid, _scope(users=["u1"]))
        # 管理员改为不含 u1 的范围
        client.put(
            f"/api/v1/assistants/{aid}/share-scope",
            headers=ADMIN,
            json={"scope": _scope(users=["u4"])},
        )
        resp = client.put(
            f"/api/v1/assistants/{aid}/subscription",
            headers=GRANTEE,
            json={"action": "resubscribe"},
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == "GRANT_INVALID"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_subscription_is_idempotent() -> None:
    aid = _create("补全测试助理订阅幂等")
    try:
        _publish(aid)
        first = client.put(
            f"/api/v1/assistants/{aid}/subscription",
            headers=GRANTEE,
            json={"action": "remove"},
        )
        second = client.put(
            f"/api/v1/assistants/{aid}/subscription",
            headers=GRANTEE,
            json={"action": "remove"},
        )
        assert second.status_code == 200
        assert second.json()["data"]["subscribeStatus"] == "removed"
        assert second.json()["data"]["subscribeTime"] == first.json()["data"]["subscribeTime"]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_subscription_invalid_action() -> None:
    aid = _create("补全测试助理非法动作")
    try:
        resp = client.put(
            f"/api/v1/assistants/{aid}/subscription",
            headers=GRANTEE,
            json={"action": "unknown"},
        )
        assert resp.status_code == 422 or resp.status_code == 400
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


# ============================ AI 生成 ============================


def _ai(**overrides) -> dict:
    data = {
        "field": "description",
        "name": "招聘面试助理",
        "categoryName": "人资",
        "description": None,
        "tags": [],
        "prompt": None,
        "quickQuestions": [],
        "currentValue": None,
        "mode": "auto",
    }
    data.update(overrides)
    return data


def test_ai_generate_description() -> None:
    resp = client.post("/api/v1/ai/generate", headers=OWNER, json=_ai())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["field"] == "description"
    assert data["mode"] == "generate"
    assert 10 <= len(data["value"]) <= 200
    assert "招聘面试助理" in data["value"]
    assert data["hitLimit"] is False


def test_ai_polish_description_auto_mode() -> None:
    resp = client.post(
        "/api/v1/ai/generate",
        headers=OWNER,
        json=_ai(currentValue="面向候选人的问答助理。"),
    )
    data = resp.json()["data"]
    assert data["mode"] == "polish"
    assert data["value"].startswith("面向候选人的问答助理")
    assert len(data["value"]) <= 200


def test_ai_generate_tags_five_unique() -> None:
    resp = client.post(
        "/api/v1/ai/generate",
        headers=OWNER,
        json=_ai(field="tags", description="负责简历筛选与面试安排，输出评估结论。"),
    )
    data = resp.json()["data"]
    assert data["mode"] == "generate"
    assert len(data["value"]) == 5
    assert len(set(data["value"])) == 5
    assert all(len(t) <= 8 for t in data["value"])


def test_ai_tags_hit_limit() -> None:
    resp = client.post(
        "/api/v1/ai/generate",
        headers=OWNER,
        json=_ai(field="tags", currentValue=["一", "二", "三", "四", "五"]),
    )
    data = resp.json()["data"]
    assert data["hitLimit"] is True
    assert data["value"] == ["一", "二", "三", "四", "五"]


def test_ai_generate_prompt() -> None:
    resp = client.post(
        "/api/v1/ai/generate",
        headers=OWNER,
        json=_ai(field="prompt", description="解释招聘流程与面试评估标准。"),
    )
    data = resp.json()["data"]
    assert "你是" in data["value"]
    assert "需人工确认" in data["value"]
    assert len(data["value"]) <= 4000


def test_ai_generate_quick_questions() -> None:
    resp = client.post("/api/v1/ai/generate", headers=OWNER, json=_ai(field="quickQuestions"))
    data = resp.json()["data"]
    assert len(data["value"]) == 6
    assert len(set(data["value"])) == 6


def test_ai_quick_questions_hit_limit() -> None:
    existing = [f"问题{i}" for i in range(6)]
    resp = client.post(
        "/api/v1/ai/generate",
        headers=OWNER,
        json=_ai(field="quickQuestions", currentValue=existing),
    )
    data = resp.json()["data"]
    assert data["hitLimit"] is True
    assert data["value"] == existing


def test_ai_invalid_field() -> None:
    resp = client.post("/api/v1/ai/generate", headers=OWNER, json=_ai(field="unknown"))
    assert resp.status_code == 422 or resp.status_code == 400


# ============================ 头像预签名 ============================


def test_avatar_presign_success() -> None:
    resp = client.post(
        "/api/v1/common/avatar-presign",
        headers=OWNER,
        json={"fileName": "avatar.png", "contentType": "image/png", "fileSize": 1048576},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["objectKey"].startswith("avatar/")
    assert data["objectKey"].endswith(".png")
    assert data["expiresIn"] == 600
    assert data["uploadUrl"]
    assert data["publicUrl"]


def test_avatar_presign_rejects_non_image() -> None:
    resp = client.post(
        "/api/v1/common/avatar-presign",
        headers=OWNER,
        json={"fileName": "a.pdf", "contentType": "application/pdf", "fileSize": 1024},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "AVATAR_TYPE_INVALID"


def test_avatar_presign_rejects_oversize() -> None:
    resp = client.post(
        "/api/v1/common/avatar-presign",
        headers=OWNER,
        json={
            "fileName": "avatar.png",
            "contentType": "image/png",
            "fileSize": 2097153,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "AVATAR_TOO_LARGE"
