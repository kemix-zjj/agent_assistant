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


# ============================ 列表范围边界 ============================


def test_mine_scope_includes_unshared_and_rejected() -> None:
    """未共享 / 已拒绝的助理只出现在「我的助理」，不出现在全部与共享。"""
    unshared = _create("补全测试助理未共享态")
    rejected = _create("补全测试助理已拒绝态")
    try:
        # 制造一条已拒绝：提交共享后由管理员拒绝
        submitted = client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [rejected], "scope": _scope(users=["u1"])},
        )
        assert submitted.status_code == 201, submitted.text
        approval_id = submitted.json()["data"]["approvalIds"][0]
        client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            headers=ADMIN,
            json={"rejectReason": "范围过大，请收敛"},
        )

        mine_ids = [
            c["assistantId"]
            for c in client.get(
                "/api/v1/assistants",
                headers=OWNER,
                params={"scope": "mine", "pageSize": 50},
            ).json()["data"]["list"]
        ]
        assert unshared in mine_ids
        assert rejected in mine_ids

        all_ids = [
            c["assistantId"]
            for c in client.get(
                "/api/v1/assistants",
                headers=OWNER,
                params={"scope": "all", "pageSize": 50},
            ).json()["data"]["list"]
        ]
        assert unshared not in all_ids
        assert rejected not in all_ids

        shared_ids = [
            c["assistantId"]
            for c in client.get(
                "/api/v1/assistants",
                headers=OWNER,
                params={"scope": "shared", "pageSize": 50},
            ).json()["data"]["list"]
        ]
        assert unshared not in shared_ids
        assert rejected not in shared_ids
    finally:
        client.delete(f"/api/v1/assistants/{unshared}", headers=OWNER)
        client.delete(f"/api/v1/assistants/{rejected}", headers=OWNER)


def test_all_scope_includes_only_effectively_shared() -> None:
    """「全部」只含本质已共享的审批中 / 已拒绝；未共享与「共享审批」两类不出现。"""
    unshared = _create("补全测试助理全部边界")
    pending_share = _create("补全测试助理共享审批中")
    approved = _create("补全测试助理调整审批中")
    rejected_share = _create("补全测试助理共享被拒")
    try:
        client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [pending_share], "scope": _scope(users=["u1"])},
        )
        _publish(approved)
        # 已共享后编辑 → 调整审批中，此时仍应计入「全部 · 已共享」
        update_body = _payload("补全测试助理调整审批中")
        update_body["changeNote"] = "调整描述"
        update = client.put(f"/api/v1/assistants/{approved}", headers=OWNER, json=update_body)
        assert update.status_code == 200, update.text
        submitted = client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [rejected_share], "scope": _scope(users=["u1"])},
        )
        client.post(
            f"/api/v1/approvals/{submitted.json()['data']['approvalIds'][0]}/reject",
            headers=ADMIN,
            json={"rejectReason": "范围过大，请收敛"},
        )

        all_rows = client.get(
            "/api/v1/assistants",
            headers=OWNER,
            params={"scope": "all", "pageSize": 50},
        ).json()["data"]["list"]
        all_ids = [c["assistantId"] for c in all_rows]
        # 调整审批中本质已共享：计入全部，角标折叠为「已共享」且不展开子类
        assert approved in all_ids
        pending_card = next(c for c in all_rows if c["assistantId"] == approved)
        assert pending_card["shareStatus"] == "approved"
        assert pending_card["pendingType"] is None
        assert unshared not in all_ids
        # 共享审批中 / 已拒绝 · 共享审批从未共享成功，只在「我的助理」展示
        assert pending_share not in all_ids
        assert rejected_share not in all_ids
    finally:
        client.delete(f"/api/v1/assistants/{unshared}", headers=OWNER)
        client.delete(f"/api/v1/assistants/{pending_share}", headers=OWNER)
        client.delete(f"/api/v1/assistants/{approved}", headers=OWNER)
        client.delete(f"/api/v1/assistants/{rejected_share}", headers=OWNER)


def test_shared_scope_excludes_own_assistants() -> None:
    """共享助理只含别人共享给我的，创建人自己不应出现在自己的共享页签。"""
    aid = _create("补全测试助理自授权")
    try:
        _publish(aid, _scope(users=["u1"]))  # u1 映射登录号 2001 李静
        grantee = _h("2001", "李静")

        grantee_shared = [
            c["assistantId"]
            for c in client.get(
                "/api/v1/assistants",
                headers=grantee,
                params={"scope": "shared", "pageSize": 50},
            ).json()["data"]["list"]
        ]
        assert aid in grantee_shared

        owner_shared = [
            c["assistantId"]
            for c in client.get(
                "/api/v1/assistants",
                headers=OWNER,
                params={"scope": "shared", "pageSize": 50},
            ).json()["data"]["list"]
        ]
        assert aid not in owner_shared
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_all_scope_three_card_kinds() -> None:
    """「全部」只应出现三类：平台预置 / 我创建的已共享 / 别人共享给我且已订阅。"""
    mine_approved = _create("补全测试助理全部三类")
    try:
        _publish(mine_approved, _scope(users=["u1"]))

        # 李静视角：平台预置 + 已订阅（别人创建）
        grantee = _h("2001", "李静")
        grantee_rows = client.get(
            "/api/v1/assistants", headers=grantee, params={"scope": "all", "pageSize": 50}
        ).json()["data"]["list"]
        for row in grantee_rows:
            if row["source"] == "platform":
                continue
            assert row["source"] == "shared", row
            assert row["subscribeStatus"] == "subscribed", row
            assert row["ownerName"] != "李静", row

        # 创建人视角：平台预置 + 自己创建的已共享（不出现 shared 视图）
        owner_rows = client.get(
            "/api/v1/assistants", headers=OWNER, params={"scope": "all", "pageSize": 50}
        ).json()["data"]["list"]
        owner_sources = {row["source"] for row in owner_rows}
        assert owner_sources <= {"platform", "custom", "thirdparty"}, owner_sources
        assert mine_approved in [row["assistantId"] for row in owner_rows]
    finally:
        client.delete(f"/api/v1/assistants/{mine_approved}", headers=OWNER)


# ============================ 列表页签口径 ============================


def test_auth_scope_removed() -> None:
    """「授权管理」页签已按需求移除，scope=auth 不再受理。"""
    resp = client.get(
        "/api/v1/assistants", headers=ADMIN, params={"scope": "auth", "pageSize": 50}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "PARAM_INVALID"


def test_rejected_shared_cannot_be_deleted() -> None:
    """已拒绝 · 调整审批（曾共享过）不可删除。"""
    aid = _create("补全测试助理已共享被拒")
    try:
        _publish(aid)
        # 已共享后编辑 → 调整审批 → 被拒
        body = {
            "name": "补全测试助理已共享被拒",
            "avatarType": "char",
            "avatarChar": "测",
            "avatarColor": "#3685F2",
            "description": "用于校验「已拒绝 · 调整审批」删除拦截的测试助理描述。",
            "tags": ["测试"],
            "categoryId": 2,
            "prompt": "你是补全测试助理。",
            "skillIds": [],
            "mcpIds": [],
            "knowledgeBaseIds": [],
            "quickQuestions": [],
            "changeNote": "调整描述",
        }
        client.put(f"/api/v1/assistants/{aid}", headers=OWNER, json=body)
        pending = client.get(
            "/api/v1/approvals", headers=ADMIN, params={"approvalType": "change"}
        ).json()["data"]["list"]
        approval_id = next(c["approvalId"] for c in pending if c["assistantId"] == aid)
        client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            headers=ADMIN,
            json={"rejectReason": "内容不足"},
        )

        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["shareStatus"] == "rejected"
        assert detail["rejectType"] == "change"
        # 四类已拒绝均展示删除入口，由详情页按子类提示不可删除
        assert "delete" in detail["actions"]

        resp = client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)
        assert resp.status_code == 409
        assert "无法删除" in resp.json()["message"]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


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


# ============================ 头像上传（本地存储） ============================

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


def test_avatar_upload_returns_short_url(monkeypatch, tmp_path) -> None:
    from app.core.config import settings

    monkeypatch.setattr(type(settings), "static_dir", property(lambda self: tmp_path))

    resp = client.post(
        "/api/v1/common/avatar-upload",
        headers=OWNER,
        files={"file": ("avatar.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["objectKey"].startswith("avatar/")
    assert data["objectKey"].endswith(".png")
    # 落盘路径可直接拼在 /static 后面，且远小于 avatarUrl 的 512 字符上限
    assert data["avatarUrl"] == f"/static/{data['objectKey']}"
    assert len(data["avatarUrl"]) < 512
    assert (tmp_path / data["objectKey"]).is_file()


def test_avatar_upload_rejects_non_image() -> None:
    resp = client.post(
        "/api/v1/common/avatar-upload",
        headers=OWNER,
        files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "AVATAR_TYPE_INVALID"


def test_avatar_upload_rejects_oversize() -> None:
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024)
    resp = client.post(
        "/api/v1/common/avatar-upload",
        headers=OWNER,
        files={"file": ("avatar.png", big, "image/png")},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "AVATAR_TOO_LARGE"
