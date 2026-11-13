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
    """分支 B：管理员直接生效，重算人员级授权；版本号仅在审批通过时推进。"""
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
        # 未共享过：管理员直改不产生版本号，仍为「未发布」
        assert detail["version"] == ""
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


# ============================ 下架申请 ============================


def _publish(aid: int) -> None:
    """提交共享并由管理员通过，使助理进入 approved。"""
    submitted = client.post(
        "/api/v1/shares",
        headers=OWNER,
        json={"assistantIds": [aid], "scope": _scope(users=["u1"])},
    )
    assert submitted.status_code == 201, submitted.text
    approval_id = submitted.json()["data"]["approvalIds"][0]
    approved = client.post(
        f"/api/v1/approvals/{approval_id}/approve", headers=ADMIN, json={}
    )
    assert approved.status_code == 200, approved.text


def test_offline_submit_moves_to_pending_offline() -> None:
    aid = _create("共享提交助理下架甲")
    try:
        _publish(aid)
        resp = client.post(
            f"/api/v1/assistants/{aid}/offline",
            headers=OWNER,
            json={"reason": "规则调整，需要下架后重建"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["shareStatus"] == "pending"
        assert data["approvalId"] > 0

        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["shareStatus"] == "pending"
        assert detail["pendingType"] == "offline"
        assert detail["versionHistory"][0]["action"] == "offline_submit"
        # 下架审批中：仅创建人可召唤，可查看授权范围；不可编辑、不可重复提交
        assert detail["actions"] == ["summon", "shareScope"]

        # 进入管理员待审批列表，类型为下架申请
        pending = client.get(
            "/api/v1/approvals",
            headers=ADMIN,
            params={"status": "pending", "approvalType": "offline", "pageSize": 50},
        ).json()["data"]["list"]
        hit = next((row for row in pending if row["assistantId"] == aid), None)
        assert hit is not None
        assert hit["approvalType"] == "offline"
        assert hit["approvalTypeName"] == "下架申请"
        assert hit["changeNote"] == "规则调整，需要下架后重建"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_offline_approve_marks_offline_and_invalidates_grants() -> None:
    aid = _create("共享提交助理下架乙")
    try:
        _publish(aid)
        # 李静（u1）此时能看到该共享助理
        before = client.get(
            "/api/v1/assistants", headers=_h("2001", "李静"), params={"scope": "shared"}
        ).json()["data"]["list"]
        assert aid in [c["assistantId"] for c in before]

        submitted = client.post(
            f"/api/v1/assistants/{aid}/offline",
            headers=OWNER,
            json={"reason": "能力合并"},
        )
        approval_id = submitted.json()["data"]["approvalId"]
        approved = client.post(
            f"/api/v1/approvals/{approval_id}/approve", headers=ADMIN, json={}
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["data"]["shareStatus"] == "offline"

        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["shareStatus"] == "offline"
        assert detail["versionHistory"][0]["action"] == "offline_approve"

        # 被授权方列表中已移除
        after = client.get(
            "/api/v1/assistants", headers=_h("2001", "李静"), params={"scope": "shared"}
        ).json()["data"]["list"]
        assert aid not in [c["assistantId"] for c in after]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_offline_reject_marks_rejected() -> None:
    """下架申请被拒：状态置为已拒绝 · 下架审批，原授权范围继续生效。"""
    aid = _create("共享提交助理下架丙")
    try:
        _publish(aid)
        submitted = client.post(
            f"/api/v1/assistants/{aid}/offline",
            headers=OWNER,
            json={"reason": "临时下架试试"},
        )
        approval_id = submitted.json()["data"]["approvalId"]
        rejected = client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            headers=ADMIN,
            json={"rejectReason": "业务仍在使用，暂不下架"},
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["data"]["shareStatus"] == "rejected"

        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["shareStatus"] == "rejected"
        assert detail["rejectType"] == "offline"
        assert detail["versionHistory"][0]["action"] == "offline_reject"
        # 已拒绝 · 下架审批：删除入口仍展示，点击时提示不可删除
        assert "delete" in detail["actions"]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_offline_submit_requires_shared_and_owner() -> None:
    aid = _create("共享提交助理下架丁")
    try:
        # 未共享不可申请下架
        resp = client.post(
            f"/api/v1/assistants/{aid}/offline", headers=OWNER, json={"reason": "测试"}
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == "ASSISTANT_STATUS_CHANGED"

        _publish(aid)
        # 非创建人不可申请下架
        denied = client.post(
            f"/api/v1/assistants/{aid}/offline", headers=OTHER, json={"reason": "测试"}
        )
        assert denied.status_code == 403
        assert denied.json()["code"] == "NO_PERMISSION"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_offline_submit_rejects_empty_reason() -> None:
    aid = _create("共享提交助理下架戊")
    try:
        _publish(aid)
        resp = client.post(
            f"/api/v1/assistants/{aid}/offline", headers=OWNER, json={"reason": "   "}
        )
        assert resp.status_code == 400
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def _take_offline(aid: int) -> None:
    """走完「共享 → 申请下架 → 管理员通过」，使助理进入 offline。"""
    _publish(aid)
    submitted = client.post(
        f"/api/v1/assistants/{aid}/offline",
        headers=OWNER,
        json={"reason": "能力合并，先下架"},
    )
    assert submitted.status_code == 201, submitted.text
    approval_id = submitted.json()["data"]["approvalId"]
    approved = client.post(
        f"/api/v1/approvals/{approval_id}/approve", headers=ADMIN, json={}
    )
    assert approved.status_code == 200, approved.text


def test_offline_can_resubmit_share() -> None:
    """已下架（offline）可重新提交共享申请，等同重新上架。"""
    aid = _create("共享提交助理下架己")
    try:
        _take_offline(aid)

        cards = client.get(
            "/api/v1/assistants", headers=OWNER, params={"scope": "mine", "pageSize": 50}
        ).json()["data"]["list"]
        card = next(c for c in cards if c["assistantId"] == aid)
        assert card["shareStatus"] == "offline"
        assert "resubmit" in card["actions"]

        # 状态筛选放行 offline，且详情与卡片同源下发 actions
        filtered = client.get(
            "/api/v1/assistants",
            headers=OWNER,
            params={"scope": "mine", "statusFilter": "offline", "pageSize": 50},
        ).json()["data"]["list"]
        assert aid in [c["assistantId"] for c in filtered]

        offline_detail = client.get(
            f"/api/v1/assistants/{aid}", headers=OWNER
        ).json()["data"]
        assert offline_detail["actions"] == ["summon", "edit", "delete", "resubmit"]

        resp = client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={
                "assistantIds": [aid],
                "scope": _scope(users=["u1"]),
                "changeNote": "下架后重新上架",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["submittedCount"] == 1
        assert data["assistantStatus"] == "pending"
        assert len(data["approvalIds"]) == 1

        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["shareStatus"] == "pending"
        assert detail["versionHistory"][0]["action"] == "share_submit"
        assert detail["shareScope"]["grantTotal"] == 1
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_detail_actions_include_offline_for_approved() -> None:
    """已共享详情下发下架入口，且与列表卡片同源。"""
    aid = _create("共享提交助理下架庚")
    try:
        _publish(aid)
        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["actions"] == ["summon", "edit", "shareScope", "offline"]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_grantee_detail_hides_owner_approval_states() -> None:
    """被授权方详情不暴露创建人侧审批中 / 已拒绝状态与拒绝原因，仅展示「已共享」。"""
    aid = _create("共享提交助理授权审批被拒")
    grantee = _h("2001", "李静")  # u1
    try:
        _publish(aid)
        # 创建人提交授权范围变更 → 管理员拒绝
        submitted = client.put(
            f"/api/v1/assistants/{aid}/share-scope",
            headers=OWNER,
            json={"scope": _scope(users=["u1", "u2"]), "changeNote": "扩大授权范围"},
        )
        assert submitted.status_code == 200, submitted.text
        approval_id = submitted.json()["data"]["approvalId"]
        assert approval_id
        rejected = client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            headers=ADMIN,
            json={"rejectReason": "范围过大，请收敛"},
        )
        assert rejected.status_code == 200, rejected.text

        # 创建人视角：已拒绝 · 授权审批，保留拒绝原因与版本记录
        owner_detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert owner_detail["shareStatus"] == "rejected"
        assert owner_detail["rejectType"] == "scope"
        assert owner_detail["rejectReason"] == "范围过大，请收敛"
        assert owner_detail["actions"] == ["summon", "resubmit", "shareScope", "delete"]

        # 被授权方视角：仅「已共享」，不暴露审批子类 / 拒绝原因等状态标识；
        # 能力组成、授权范围、版本记录等基础信息与创建人一致可见
        grantee_detail = client.get(f"/api/v1/assistants/{aid}", headers=grantee).json()["data"]
        assert grantee_detail["shareStatus"] == "approved"
        assert grantee_detail["pendingType"] is None
        assert grantee_detail["rejectType"] is None
        assert grantee_detail["rejectReason"] is None
        assert grantee_detail["offlineReason"] is None
        assert grantee_detail["prompt"] == owner_detail["prompt"]
        assert grantee_detail["skills"] == owner_detail["skills"]
        assert grantee_detail["mcps"] == owner_detail["mcps"]
        assert grantee_detail["knowledgeBases"] == owner_detail["knowledgeBases"]
        assert grantee_detail["shareScope"] is not None
        assert grantee_detail["versionHistory"] == owner_detail["versionHistory"]
        assert grantee_detail["actions"] == ["summon", "remove"]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_status_filter_supports_all_share_states() -> None:
    """我的助理状态筛选放行全部 5 种共享状态，未知值仍拒绝。"""
    for status in ("unshared", "pending", "approved", "rejected", "offline"):
        resp = client.get(
            "/api/v1/assistants",
            headers=OWNER,
            params={"scope": "mine", "statusFilter": status},
        )
        assert resp.status_code == 200, status

    bad = client.get(
        "/api/v1/assistants",
        headers=OWNER,
        params={"scope": "mine", "statusFilter": "not-a-status"},
    )
    assert bad.status_code == 400
    assert bad.json()["code"] == "PARAM_INVALID"
