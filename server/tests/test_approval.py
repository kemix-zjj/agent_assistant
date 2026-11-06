"""审批中心接口测试（docs/03 §7.1 ~ §7.6）。

覆盖：列表与角标权限、详情（含调整后差量）、审批前调整范围、
通过（授权展开/状态流转/版本记录）、拒绝（原因校验/不写授权）、幂等与并发。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import engine
from app.main import app

client = TestClient(app)


def _h(user_id: str, name: str, dept: str | None = None) -> dict[str, str]:
    from urllib.parse import quote

    headers = {"X-User-Id": user_id, "X-User-Name": quote(name)}
    if dept:
        headers["X-User-Dept"] = quote(dept)
    return headers


OWNER = _h("1001", "王晓明", "人力资源部 · 招聘组")
ADMIN = _h("9001", "王建国", "经营管理中心")
OTHER = _h("1002", "李静")


def _payload(name: str) -> dict:
    return {
        "name": name,
        "avatarType": "char",
        "avatarChar": "审",
        "avatarColor": "#3685F2",
        "description": "用于审批中心测试的助理，描述长度满足校验要求。",
        "tags": ["审批"],
        "categoryId": 2,
        "prompt": "你是审批测试助理。",
        "skillIds": ["s4"],
        "mcpIds": ["m3"],
        "knowledgeBaseIds": ["k3"],
        "quickQuestions": [],
    }


def _scope(**overrides) -> dict:
    data = {"scopeMode": "RANGE", "orgs": [], "roles": [], "positions": [], "users": []}
    data.update(overrides)
    return data


def _create_and_submit(name: str, scope: dict | None = None) -> tuple[int, int]:
    """返回 (assistantId, approvalId)。"""
    created = client.post("/api/v1/assistants", headers=OWNER, json=_payload(name))
    assert created.status_code == 201, created.text
    aid = created.json()["data"]["assistantId"]

    submitted = client.post(
        "/api/v1/shares",
        headers=OWNER,
        json={"assistantIds": [aid], "scope": scope or _scope(users=["u1"])},
    )
    assert submitted.status_code == 201, submitted.text
    return aid, submitted.json()["data"]["approvalIds"][0]


# ============================ 列表与角标 ============================


def test_approval_list_requires_admin() -> None:
    resp = client.get("/api/v1/approvals", headers=OWNER)
    assert resp.status_code == 403
    assert resp.json()["code"] == "NO_PERMISSION"


def test_approval_list_returns_pending() -> None:
    aid, approval_id = _create_and_submit("审批测试助理甲")
    try:
        resp = client.get("/api/v1/approvals", headers=ADMIN)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1
        card = next(c for c in data["list"] if c["approvalId"] == approval_id)
        assert card["approvalType"] == "share"
        assert card["approvalTypeName"] == "共享申请"
        assert card["assistantId"] == aid
        assert card["AssistantAvatar"]["char"] == "审"
        assert card["submitterName"] == "王晓明"
        assert card["scopeSummary"].endswith("人")
        assert card["scopeMode"] == "RANGE"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_approval_filter_by_type() -> None:
    aid, _ = _create_and_submit("审批测试助理乙")
    try:
        resp = client.get(
            "/api/v1/approvals", headers=ADMIN, params={"approvalType": "scope_change"}
        )
        assert resp.status_code == 200
        assert all(c["approvalType"] == "scope_change" for c in resp.json()["data"]["list"])
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_pending_count_matches_list_total() -> None:
    aid, _ = _create_and_submit("审批测试助理丙")
    try:
        count = client.get("/api/v1/approvals/pending-count", headers=ADMIN).json()["data"]
        total = client.get("/api/v1/approvals", headers=ADMIN).json()["data"]["total"]
        assert count["pendingCount"] == total
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


# ============================ 详情 ============================


def test_approval_detail_contains_config_and_scope() -> None:
    aid, approval_id = _create_and_submit("审批测试助理丁", _scope(orgs=["O11"]))
    try:
        resp = client.get(f"/api/v1/approvals/{approval_id}", headers=ADMIN)
        assert resp.status_code == 200
        detail = resp.json()["data"]
        assert detail["status"] == "pending"
        assert detail["assistant"]["prompt"] == "你是审批测试助理。"
        assert detail["assistant"]["skills"][0]["name"] == "制度条款检索"
        assert detail["assistant"]["mcps"][0]["name"] == "考勤打卡服务"
        assert detail["scope"]["grantTotal"] == 2
        assert detail["scopeAdjusted"] is False
        assert detail["scopeDiff"] is None
        assert detail["assistantConfigChanged"] is False
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_approval_detail_not_found() -> None:
    resp = client.get("/api/v1/approvals/999999", headers=ADMIN)
    assert resp.status_code == 404
    assert resp.json()["code"] == "APPROVAL_NOT_FOUND"


# ============================ 审批前调整范围 ============================


def test_adjust_scope_creates_diff_without_applying() -> None:
    aid, approval_id = _create_and_submit("审批测试助理戊", _scope(orgs=["O11"]))
    try:
        resp = client.put(
            f"/api/v1/approvals/{approval_id}/scope",
            headers=ADMIN,
            json={"scope": _scope(users=["u5", "u6"])},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["scopeAdjusted"] is True
        assert data["scope"]["grantTotal"] == 2
        assert data["scopeDiff"]["addedCount"] == 2
        assert data["scopeDiff"]["removedCount"] == 1  # 移除组织 O11
        assert {i["dim"] for i in data["scopeDiff"]["added"]} == {"user"}
        assert data["scopeDiff"]["removed"][0]["id"] == "O11"

        # 助理仍为 pending，授权未写入
        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["shareStatus"] == "pending"
        shared = client.get(
            "/api/v1/assistants", headers=_h("2005", "周涛"), params={"scope": "shared"}
        ).json()["data"]
        assert aid not in [c["assistantId"] for c in shared["list"]]

        # 详情显示已调整并带差量
        ad = client.get(f"/api/v1/approvals/{approval_id}", headers=ADMIN).json()["data"]
        assert ad["scopeAdjusted"] is True
        assert ad["scope"]["grantTotal"] == 2
        assert ad["scopeDiff"]["addedCount"] == 2
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_adjust_scope_rejects_empty_range() -> None:
    aid, approval_id = _create_and_submit("审批测试助理己")
    try:
        resp = client.put(
            f"/api/v1/approvals/{approval_id}/scope",
            headers=ADMIN,
            json={"scope": _scope()},
        )
        assert resp.status_code == 400
        assert "至少保留一个" in resp.json()["message"]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_adjust_scope_switches_to_public() -> None:
    aid, approval_id = _create_and_submit("审批测试助理庚", _scope(users=["u1"]))
    try:
        resp = client.put(
            f"/api/v1/approvals/{approval_id}/scope",
            headers=ADMIN,
            json={"scope": _scope(scopeMode="PUBLIC")},
        )
        data = resp.json()["data"]
        assert data["scope"]["scopeMode"] == "PUBLIC"
        assert data["scope"]["grantTotal"] == 6
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


# ============================ 审批通过 ============================


def test_approve_applies_scope_and_grants() -> None:
    aid, approval_id = _create_and_submit(
        "审批测试助理辛", _scope(orgs=["O11"], users=["u3"])
    )
    try:
        resp = client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            headers=ADMIN,
            json={"comment": "同意共享"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "approved"
        assert data["shareStatus"] == "approved"
        assert data["grantTotal"] == 3  # u1, u2（组织）+ u3（直接添加）

        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["shareStatus"] == "approved"
        assert detail["version"] == "v1.1"
        assert detail["versionHistory"][0]["action"] == "share_approve"

        # 被授权方出现在共享助理列表
        for login_id, name in (("2001", "李静"), ("2003", "陈志远")):
            shared = client.get(
                "/api/v1/assistants",
                headers=_h(login_id, name),
                params={"scope": "shared", "pageSize": 50},
            ).json()["data"]
            assert aid in [c["assistantId"] for c in shared["list"]], name

        # 列表不再出现该审批
        listed = client.get("/api/v1/approvals", headers=ADMIN).json()["data"]
        assert approval_id not in [c["approvalId"] for c in listed["list"]]

        # C-03 / C-08：审批通过必须落一张 stage=effective 快照
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT stage, approval_id FROM share_scope"
                    " WHERE assistant_id = :aid AND stage = 'effective'"
                    " ORDER BY id DESC LIMIT 1"
                ),
                {"aid": aid},
            ).first()
        assert row is not None, "审批通过后应生成 stage=effective 的范围快照"
        assert row[1] == approval_id
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_approve_uses_adjusted_scope() -> None:
    aid, approval_id = _create_and_submit("审批测试助理壬", _scope(users=["u1"]))
    try:
        client.put(
            f"/api/v1/approvals/{approval_id}/scope",
            headers=ADMIN,
            json={"scope": _scope(users=["u4"])},
        )
        resp = client.post(
            f"/api/v1/approvals/{approval_id}/approve", headers=ADMIN, json={}
        )
        assert resp.json()["data"]["grantTotal"] == 1

        shared = client.get(
            "/api/v1/assistants", headers=_h("2004", "赵敏"), params={"scope": "shared"}
        ).json()["data"]
        assert aid in [c["assistantId"] for c in shared["list"]]

        # 原申请人 u1 未被授权
        not_shared = client.get(
            "/api/v1/assistants", headers=_h("2001", "李静"), params={"scope": "shared"}
        ).json()["data"]
        assert aid not in [c["assistantId"] for c in not_shared["list"]]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_approve_twice_is_idempotent() -> None:
    """条件更新受影响行数为 0 时返回首次结果，不重复展开授权。"""
    aid, approval_id = _create_and_submit("审批测试助理癸", _scope(users=["u1"]))
    try:
        first = client.post(
            f"/api/v1/approvals/{approval_id}/approve", headers=ADMIN, json={}
        )
        assert first.status_code == 200

        second = client.post(
            f"/api/v1/approvals/{approval_id}/approve", headers=ADMIN, json={}
        )
        assert second.status_code == 200
        assert second.json()["data"]["status"] == "approved"
        assert second.json()["data"]["grantTotal"] == first.json()["data"]["grantTotal"]

        # 版本只升一次
        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["version"] == "v1.1"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_approve_requires_admin() -> None:
    aid, approval_id = _create_and_submit("审批测试助理子")
    try:
        resp = client.post(
            f"/api/v1/approvals/{approval_id}/approve", headers=OWNER, json={}
        )
        assert resp.status_code == 403
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


# ============================ 审批拒绝 ============================


def test_reject_sets_reason_and_keeps_unshared_grants() -> None:
    aid, approval_id = _create_and_submit("审批测试助理丑", _scope(users=["u1"]))
    try:
        reason = "授权范围包含外协单位组织节点，请收敛至本公司部门后重新提交。"
        resp = client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            headers=ADMIN,
            json={"rejectReason": reason},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "rejected"
        assert data["shareStatus"] == "rejected"
        assert data["rejectReason"] == reason

        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["shareStatus"] == "rejected"
        assert detail["versionHistory"][0]["action"] == "share_reject"

        card = client.get(
            "/api/v1/assistants", headers=OWNER, params={"scope": "mine"}
        ).json()["data"]["list"]
        hit = next(c for c in card if c["assistantId"] == aid)
        assert hit["rejectReason"] == reason
        assert hit["actions"] == ["summon", "edit", "delete", "resubmit"]

        # 拒绝不写授权
        shared = client.get(
            "/api/v1/assistants", headers=_h("2001", "李静"), params={"scope": "shared"}
        ).json()["data"]
        assert aid not in [c["assistantId"] for c in shared["list"]]
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_reject_requires_reason() -> None:
    aid, approval_id = _create_and_submit("审批测试助理寅")
    try:
        resp = client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            headers=ADMIN,
            json={"rejectReason": ""},
        )
        assert resp.status_code == 400
        assert resp.json()["code"] in {"PARAM_INVALID", "REJECT_REASON_REQUIRED"}
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_reject_reason_too_long() -> None:
    aid, approval_id = _create_and_submit("审批测试助理卯")
    try:
        resp = client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            headers=ADMIN,
            json={"rejectReason": "长" * 201},
        )
        assert resp.status_code == 400
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_reject_then_resubmit_clears_reject_reason() -> None:
    """被拒后重新提交：状态回到 pending，卡片不再展示原拒绝原因。"""
    aid, approval_id = _create_and_submit("审批测试助理辰", _scope(users=["u1"]))
    try:
        client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            headers=ADMIN,
            json={"rejectReason": "范围过大，请收敛"},
        )
        again = client.post(
            "/api/v1/shares",
            headers=OWNER,
            json={"assistantIds": [aid], "scope": _scope(users=["u2"])},
        )
        assert again.status_code == 201

        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["shareStatus"] == "pending"
        assert detail["shareScope"]["grantTotal"] == 1
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


def test_decision_on_handled_approval_conflicts() -> None:
    """已通过的申请再次拒绝 → APPROVAL_ALREADY_HANDLED。"""
    aid, approval_id = _create_and_submit("审批测试助理巳", _scope(users=["u1"]))
    try:
        client.post(f"/api/v1/approvals/{approval_id}/approve", headers=ADMIN, json={})
        resp = client.post(
            f"/api/v1/approvals/{approval_id}/reject",
            headers=ADMIN,
            json={"rejectReason": "反悔"},
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == "APPROVAL_ALREADY_HANDLED"
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)


# ============================ 范围变更审批 ============================


def test_scope_change_approval_flow() -> None:
    """创建人调整已共享助理 → 审批通过后生效。"""
    aid, approval_id = _create_and_submit("审批测试助理午", _scope(users=["u1"]))
    try:
        client.post(f"/api/v1/approvals/{approval_id}/approve", headers=ADMIN, json={})

        # 创建人提交范围变更
        change = client.put(
            f"/api/v1/assistants/{aid}/share-scope",
            headers=OWNER,
            json={"scope": _scope(users=["u1", "u2"]), "changeNote": "扩大范围"},
        )
        assert change.status_code == 200, change.text
        change_data = change.json()["data"]
        assert change_data["applied"] is False
        change_approval_id = change_data["approvalId"]

        # 审批通过前，u2 仍不可见
        before = client.get(
            "/api/v1/assistants", headers=_h("2002", "林晓"), params={"scope": "shared"}
        ).json()["data"]
        assert aid not in [c["assistantId"] for c in before["list"]]

        decision = client.post(
            f"/api/v1/approvals/{change_approval_id}/approve",
            headers=ADMIN,
            json={"comment": "同意扩大"},
        )
        assert decision.status_code == 200
        assert decision.json()["data"]["grantTotal"] == 2

        after = client.get(
            "/api/v1/assistants", headers=_h("2002", "林晓"), params={"scope": "shared"}
        ).json()["data"]
        assert aid in [c["assistantId"] for c in after["list"]]

        detail = client.get(f"/api/v1/assistants/{aid}", headers=OWNER).json()["data"]
        assert detail["shareStatus"] == "approved"
        assert detail["shareScope"]["grantTotal"] == 2
    finally:
        client.delete(f"/api/v1/assistants/{aid}", headers=OWNER)
