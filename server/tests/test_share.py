"""共享范围展开与共享提交接口测试（docs/03 §5.1 ~ §6.3）。

覆盖：组织树/角色/岗位/人员查询、四维展开去重与来源标注、上限校验、
共享提交校验顺序与副作用、范围回显、管理员直改与创建人走审批两条分支。
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _h(user_id: str, name: str, dept: str | None = None) -> dict[str, str]:
    from urllib.parse import quote

    headers = {"X-User-Id": user_id, "X-User-Name": quote(name)}
    if dept:
        headers["X-User-Dept"] = quote(dept)
    return headers


OWNER = _h("1001", "王晓明", "人力资源部 · 招聘组")
OTHER = _h("1002", "李静", "人力资源部 · 招聘组")
ADMIN = _h("9001", "王建国", "经营管理中心")


def _payload(name: str) -> dict:
    return {
        "name": name,
        "avatarType": "char",
        "avatarChar": "共",
        "avatarColor": "#3685F2",
        "description": "用于共享提交与范围展开测试的助理，描述长度满足校验要求。",
        "tags": ["共享"],
        "categoryId": 2,
        "prompt": "你是共享测试助理。",
        "skillIds": [],
        "mcpIds": [],
        "knowledgeBaseIds": [],
        "quickQuestions": [],
    }


def _create(name: str) -> int:
    resp = client.post("/api/v1/assistants", headers=OWNER, json=_payload(name))
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["assistantId"]


def _scope(**overrides) -> dict:
    data = {"scopeMode": "RANGE", "orgs": [], "roles": [], "positions": [], "users": []}
    data.update(overrides)
    return data


# ============================ 主数据 ============================


def test_org_tree_returns_nested_nodes() -> None:
    resp = client.get("/api/v1/scopes/org-tree", headers=OWNER)
    assert resp.status_code == 200
    tree = resp.json()["data"]["tree"]
    assert tree[0]["id"] == "O1"
    assert tree[0]["children"][0]["name"] == "人力资源部"


def test_org_tree_keyword_keeps_ancestors() -> None:
    resp = client.get("/api/v1/scopes/org-tree", headers=OWNER, params={"keyword": "招聘"})
    tree = resp.json()["data"]["tree"]
    # 命中「招聘组」时保留 O1 → O11 祖先链
    assert tree[0]["id"] == "O1"
    hr = tree[0]["children"][0]
    assert hr["name"] == "人力资源部"
    assert [c["name"] for c in hr["children"]] == ["招聘组"]


def test_roles_and_positions() -> None:
    roles = client.get("/api/v1/scopes/roles", headers=OWNER).json()["data"]["list"]
    positions = client.get("/api/v1/scopes/positions", headers=OWNER).json()["data"]["list"]
    assert len(roles) == 4
    assert roles[0]["desc"]
    assert len(positions) == 3


def test_users_search_by_keyword_and_org() -> None:
    resp = client.get("/api/v1/scopes/users", headers=OWNER, params={"keyword": "李静"})
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["list"][0]["jobNo"] == "E0231"

    # 组织含下级：O11（人力资源部）应覆盖招聘组与薪酬绩效组
    by_org = client.get(
        "/api/v1/scopes/users", headers=OWNER, params={"orgIds": "O11"}
    ).json()["data"]
    assert by_org["total"] == 2


# ============================ 四维展开 ============================


def test_expand_org_includes_subordinates() -> None:
    resp = client.post(
        "/api/v1/scopes/expand",
        headers=OWNER,
        json=_scope(orgs=["O11"]),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    # 人力资源部含招聘组(u1)与薪酬绩效组(u2)
    assert data["grantTotal"] == 2
    assert {u["id"] for u in data["users"]} == {"u1", "u2"}
    assert data["counts"] == {"org": 1, "role": 0, "position": 0, "user": 0}


def test_expand_dedupes_and_marks_all_sources() -> None:
    resp = client.post(
        "/api/v1/scopes/expand",
        headers=OWNER,
        json=_scope(orgs=["O11"], roles=["r1"], users=["u1"]),
    )
    data = resp.json()["data"]
    u1 = next(u for u in data["users"] if u["id"] == "u1")
    # u1 同时被组织、角色、直接添加命中，只出现一次且三个来源都标注
    assert u1["sources"] == ["org", "role", "user"]
    assert data["grantTotal"] == 2


def test_expand_multi_dimension_union() -> None:
    resp = client.post(
        "/api/v1/scopes/expand",
        headers=OWNER,
        json=_scope(orgs=["O11"], positions=["p2"], users=["u6"]),
    )
    data = resp.json()["data"]
    ids = {u["id"] for u in data["users"]}
    # O11 → u1,u2；p2（主管）→ u3；直接添加 → u6
    assert ids == {"u1", "u2", "u3", "u6"}
    assert data["grantTotal"] == 4


def test_expand_public_mode_returns_headcount() -> None:
    resp = client.post(
        "/api/v1/scopes/expand",
        headers=OWNER,
        json=_scope(scopeMode="PUBLIC", orgs=["O11"]),
    )
    data = resp.json()["data"]
    assert data["scopeMode"] == "PUBLIC"
    assert data["grantTotal"] == 6


def test_expand_rejects_over_limit() -> None:
    resp = client.post(
        "/api/v1/scopes/expand",
        headers=OWNER,
        json=_scope(users=[f"u{i}" for i in range(201)]),
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "SHARE_SCOPE_EXCEED_LIMIT"
    assert body["data"]["exceeded"]["user"] == 201


# ============================ 提交共享 ============================


def test_submit_creates_pending_approval() -> None:
    aid = _create("共享提交助理甲")
    try:
        resp = client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={
                "assistantIds": [aid],
                "scope": _scope(orgs=["O11"], users=["u5"]),
                "changeNote": "首次申请共享",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["submittedCount"] == 1
        assert data["assistantStatus"] == "pending"
        assert len(data["approvalIds"]) == 1
        assert data["batchNo"].startswith("B")

        # 助理状态变为 pending，卡片 actions 不再含 share
        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["shareStatus"] == "pending"
        assert detail["versionHistory"][0]["action"] == "share_submit"
        assert detail["shareScope"]["grantTotal"] == 3

        # 进行中的范围变更不应被允许（助理处于 pending）
        update = client.put(
            f"/api/v1/assistants/{aid}/share-scope",
            headers=OWNER,
            json={"scope": _scope(users=["u1"])},
        )
        assert update.status_code == 409
        assert update.json()["code"] == "SHARE_SCOPE_IMMUTABLE"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_submit_batch_shares_batch_no() -> None:
    ids = [_create("共享提交助理乙"), _create("共享提交助理丙")]
    try:
        resp = client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": ids, "scope": _scope(users=["u1"])},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["submittedCount"] == 2
        assert len(set(data["approvalIds"])) == 2
    finally:
        for aid in ids:
            client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_submit_rejects_empty_scope() -> None:
    aid = _create("共享提交助理丁")
    try:
        resp = client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [aid], "scope": _scope()},
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "PARAM_INVALID"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_submit_public_mode_needs_no_scope() -> None:
    aid = _create("共享提交助理戊")
    try:
        resp = client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [aid], "scope": _scope(scopeMode="PUBLIC")},
        )
        assert resp.status_code == 201
        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["shareScope"]["scopeMode"] == "PUBLIC"
        assert detail["shareScope"]["grantTotal"] == 6
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_submit_rejects_non_owner() -> None:
    aid = _create("共享提交助理己")
    try:
        resp = client.post(
            "/api/v1/shares",
            headers=OTHER,
            json={"assistantIds": [aid], "scope": _scope(users=["u1"])},
        )
        assert resp.status_code == 403
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_submit_rejects_duplicate_submission() -> None:
    aid = _create("共享提交助理庚")
    try:
        first = client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [aid], "scope": _scope(users=["u1"])},
        )
        assert first.status_code == 201

        second = client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [aid], "scope": _scope(users=["u2"])},
        )
        assert second.status_code == 409
        assert second.json()["code"] == "ASSISTANT_ALREADY_SHARED"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_submit_rejects_unknown_assistant() -> None:
    resp = client.post(
        "/api/v1/shares",
        headers=OWNER,
        json={"assistantIds": [999999], "scope": _scope(users=["u1"])},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ASSISTANT_NOT_FOUND"


def test_submit_is_atomic_on_partial_failure() -> None:
    """批量提交中若有一个助理状态已变更，整批失败（文档 Q-09）。"""
    ok_id = _create("共享提交助理辛")
    pending_id = _create("共享提交助理壬")
    try:
        client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [pending_id], "scope": _scope(users=["u1"])},
        )

        resp = client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [ok_id, pending_id], "scope": _scope(users=["u2"])},
        )
        assert resp.status_code == 409

        # 成功的那个助理未被改为 pending，保持 unshared
        detail = client.get(f"/api/v1/assistants/{ok_id}", headers=OWNER).json()["data"]
        assert detail["shareStatus"] == "unshared"
    finally:
        client.delete(f"/api/v1/assistants/{ok_id}", headers=OWNER)
        client.delete(f"/api/v1/assistants/{pending_id}", headers=OWNER)


def test_submit_writes_audit_log() -> None:
    """副作用第 5 项：写 sys_audit_log（含变更前后范围快照）。"""
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.system import SysAuditLog

    aid = _create("共享提交助理审计")
    try:
        client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [aid], "scope": _scope(users=["u1"])},
        )
        db = SessionLocal()
        try:
            rows = db.scalars(
                select(SysAuditLog).where(
                    SysAuditLog.action == "share_submit",
                    SysAuditLog.object_id == str(aid),
                )
            ).all()
            assert len(rows) == 1
            assert rows[0].before_value == {"shareStatus": "unshared"}
            assert rows[0].after_value["shareStatus"] == "pending"
            assert rows[0].after_value["grantTotal"] == 1
            assert rows[0].operator_name == "王晓明"
        finally:
            db.close()
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


# ============================ 范围回显与调整 ============================


def test_share_scope_readonly_for_non_owner() -> None:
    aid = _create("共享范围助理甲")
    try:
        client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [aid], "scope": _scope(users=["u1"])},
        )
        resp = client.get(f"/api/v1/assistants/{aid}/share-scope", headers=OTHER)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["editable"] is False
        assert data["editableBy"] == "none"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_admin_scope_update_applies_directly() -> None:
    """分支 B：管理员直接生效，重算人员级授权并升版本。"""
    aid = _create("共享范围助理戊")
    try:
        resp = client.put(
            f"/api/v1/assistants/{aid}/share-scope",
            headers=ADMIN,
            json={"scope": _scope(orgs=["O11"]), "changeNote": "管理员直改"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["applied"] is True
        assert data["approvalId"] is None
        assert data["scope"]["grantTotal"] == 2

        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["version"] == "v1.1"
        assert detail["versionHistory"][0]["action"] == "scope_change"
        assert detail["shareScope"]["grantTotal"] == 2

        # 被授权方（李静 → 主数据 u1）出现在「共享助理」列表
        shared = client.get(
            "/api/v1/assistants",
            headers=_h("2001", "李静"),
            params={"scope": "shared", "pageSize": 50},
        ).json()["data"]
        assert aid in [c["assistantId"] for c in shared["list"]]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_admin_scope_update_invalidates_removed_grants() -> None:
    """范围收紧后，未命中人员置 invalid 而非物理删除（C-05）。"""
    aid = _create("共享范围助理己")
    try:
        client.put(
            f"/api/v1/assistants/{aid}/share-scope",
            headers=ADMIN,
            json={"scope": _scope(users=["u1", "u2"])},
        )
        client.put(
            f"/api/v1/assistants/{aid}/share-scope",
            headers=ADMIN,
            json={"scope": _scope(users=["u1"])},
        )

        # u2 的「共享助理」列表不再出现，但授权记录保留为 invalid
        shared_user2 = client.get(
            "/api/v1/assistants", headers=_h("2002", "林晓"), params={"scope": "shared"}
        ).json()["data"]
        assert aid not in [c["assistantId"] for c in shared_user2["list"]]

        shared_user1 = client.get(
            "/api/v1/assistants", headers=_h("2001", "李静"), params={"scope": "shared"}
        ).json()["data"]
        assert aid in [c["assistantId"] for c in shared_user1["list"]]
        assert shared_user1["list"][0]["actions"] == ["summon", "remove"]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_scope_update_blocked_while_pending() -> None:
    aid = _create("共享范围助理庚")
    try:
        client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [aid], "scope": _scope(users=["u1"])},
        )
        resp = client.put(
            f"/api/v1/assistants/{aid}/share-scope",
            headers=ADMIN,
            json={"scope": _scope(orgs=["O11"])},
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == "SHARE_SCOPE_IMMUTABLE"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_scope_update_requires_permission() -> None:
    aid = _create("共享范围助理丙")
    try:
        resp = client.put(
            f"/api/v1/assistants/{aid}/share-scope",
            headers=OTHER,
            json={"scope": _scope(users=["u1"])},
        )
        assert resp.status_code == 403
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_scope_update_rejects_empty_range() -> None:
    aid = _create("共享范围助理丁")
    try:
        resp = client.put(
            f"/api/v1/assistants/{aid}/share-scope",
            headers=ADMIN,
            json={"scope": _scope()},
        )
        assert resp.status_code == 400
        assert "至少保留一个" in resp.json()["message"]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)
