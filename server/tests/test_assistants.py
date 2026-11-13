"""助理 CRUD 接口测试（对应 docs/03 §3.1 ~ §3.6）。

覆盖：列表三范围、详情、创建校验、编辑版本与权限、删除影响面与级联。
依赖数据库中的 6 条平台预置演示数据；测试自建数据在结束时清理。
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _h(user_id: str, name: str, dept: str | None = None) -> dict[str, str]:
    """HTTP 头只能是 ASCII，中文姓名按 UTF-8 百分号编码后传入。"""
    from urllib.parse import quote

    headers = {"X-User-Id": user_id, "X-User-Name": quote(name)}
    if dept:
        headers["X-User-Dept"] = quote(dept)
    return headers


OWNER = _h("1001", "王晓明", "人力资源部 · 招聘组")
OTHER = _h("1002", "李静", "人力资源部 · 招聘组")
ADMIN = {**_h("9001", "王建国"), "X-Company-Id": "1"}


def _payload(name: str, **overrides) -> dict:
    data = {
        "name": name,
        "avatarType": "char",
        "avatarChar": "测",
        "avatarUrl": None,
        "avatarColor": "#3685F2",
        "description": "用于接口测试的助理，覆盖创建、编辑、删除与列表查询链路。",
        "tags": ["测试", "接口"],
        "categoryId": 2,
        "prompt": "你是测试助理，负责验证接口契约。",
        "skillIds": ["s1", "s4"],
        "mcpIds": ["m2"],
        "knowledgeBaseIds": ["k1"],
        "quickQuestions": ["这个助理怎么用？", "支持哪些场景？"],
    }
    data.update(overrides)
    return data


@pytest.fixture
def created_ids() -> list[int]:
    ids: list[int] = []
    yield ids
    for assistant_id in ids:
        client.delete(f"/api/v1/assistants/{assistant_id}", headers=OWNER)


def _create(name: str, **overrides) -> dict:
    resp = client.post("/api/v1/assistants", headers=OWNER, json=_payload(name, **overrides))
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# ============================ 列表 ============================


def test_list_all_contains_platform_seed() -> None:
    resp = client.get("/api/v1/assistants", headers=OWNER, params={"scope": "all"})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["page"] == 1
    assert body["pageSize"] == 12
    assert body["total"] >= 6
    sources = {card["source"] for card in body["list"]}
    assert "platform" in sources
    # 平台预置排在最前（rank=0）
    assert body["list"][0]["source"] == "platform"


def test_list_mine_is_empty_for_new_user() -> None:
    resp = client.get("/api/v1/assistants", headers=OTHER, params={"scope": "mine"})
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 0


def test_list_rejects_invalid_scope() -> None:
    resp = client.get("/api/v1/assistants", headers=OWNER, params={"scope": "unknown"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "PARAM_INVALID"
    assert resp.json()["data"]["field"] == "scope"


def test_list_card_has_no_prompt_field() -> None:
    resp = client.get("/api/v1/assistants", headers=OWNER, params={"scope": "all"})
    card = resp.json()["data"]["list"][0]
    assert "prompt" not in card
    assert card["descriptionTruncated"]
    assert isinstance(card["actions"], list)


def test_list_filters_by_category() -> None:
    resp = client.get(
        "/api/v1/assistants", headers=OWNER, params={"scope": "all", "categoryId": 2}
    )
    assert resp.status_code == 200
    assert all(c["categoryId"] == 2 for c in resp.json()["data"]["list"])


def test_list_keyword_hits_tag() -> None:
    resp = client.get(
        "/api/v1/assistants", headers=OWNER, params={"scope": "all", "keyword": "纪要"}
    )
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()["data"]["list"]]
    assert any("会议" in n for n in names)


# ============================ 创建 ============================


def test_create_returns_unshared_unpublished(created_ids: list[int]) -> None:
    data = _create("接口测试助理甲")
    created_ids.append(data["assistantId"])

    assert data["shareStatus"] == "unshared"
    # 未共享不产生版本号，页面展示「未发布」
    assert data["version"] == ""
    assert data["hasShared"] is False
    assert data["source"] == "custom"
    assert data["ownerName"] == "王晓明"
    assert data["categoryName"] == "人资"
    assert data["tags"] == ["测试", "接口"]
    assert [s["id"] for s in data["skills"]] == ["s1", "s4"]
    assert data["mcps"][0]["name"] == "HR 主数据服务"
    assert data["knowledgeBases"][0]["name"] == "招聘管理制度库"
    assert data["versionHistory"][0]["action"] == "create"


def test_create_rejects_duplicate_name(created_ids: list[int]) -> None:
    data = _create("接口测试助理乙")
    created_ids.append(data["assistantId"])

    resp = client.post("/api/v1/assistants", headers=OWNER, json=_payload("接口测试助理乙"))
    assert resp.status_code == 409
    assert resp.json()["code"] == "ASSISTANT_NAME_DUPLICATED"
    assert resp.json()["data"]["field"] == "name"


def test_create_rejects_unknown_category() -> None:
    resp = client.post(
        "/api/v1/assistants", headers=OWNER, json=_payload("接口测试助理丙", categoryId=999)
    )
    assert resp.status_code == 400
    assert resp.json()["data"]["field"] == "categoryId"


def test_create_rejects_short_description() -> None:
    resp = client.post(
        "/api/v1/assistants", headers=OWNER, json=_payload("接口测试助理丁", description="太短")
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "PARAM_INVALID"


def test_create_rejects_too_many_tags() -> None:
    resp = client.post(
        "/api/v1/assistants",
        headers=OWNER,
        json=_payload("接口测试助理戊", tags=["1", "2", "3", "4", "5", "6"]),
    )
    assert resp.status_code == 400


def test_create_rejects_offline_skill() -> None:
    resp = client.post(
        "/api/v1/assistants", headers=OWNER, json=_payload("接口测试助理己", skillIds=["s999"])
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "RESOURCE_UNAVAILABLE"
    assert resp.json()["data"]["field"] == "skillIds"


# ============================ 详情 ============================


def test_detail_returns_prompt_for_owner(created_ids: list[int]) -> None:
    data = _create("接口测试助理庚")
    created_ids.append(data["assistantId"])

    resp = client.get(f"/api/v1/assistants/{data['assistantId']}", headers=OWNER)
    assert resp.status_code == 200
    detail = resp.json()["data"]
    assert detail["prompt"] == "你是测试助理，负责验证接口契约。"
    assert detail["quickQuestions"] == ["这个助理怎么用？", "支持哪些场景？"]


def test_detail_not_found() -> None:
    resp = client.get("/api/v1/assistants/999999", headers=OWNER)
    assert resp.status_code == 404
    assert resp.json()["code"] == "ASSISTANT_NOT_FOUND"


# ============================ 编辑 ============================


def test_update_unshared_keeps_unpublished_version(created_ids: list[int]) -> None:
    data = _create("接口测试助理辛")
    created_ids.append(data["assistantId"])

    resp = client.put(
        f"/api/v1/assistants/{data['assistantId']}",
        headers=OWNER,
        json=_payload("接口测试助理辛", description="编辑后的描述，长度足够通过校验要求。"),
    )
    assert resp.status_code == 200
    updated = resp.json()["data"]
    # 未共享助理编辑直接生效，不产生版本号
    assert updated["version"] == ""
    assert updated["shareStatus"] == "unshared"
    assert updated["description"].startswith("编辑后的描述")
    assert updated["versionHistory"][0]["action"] == "update"


def test_update_rejects_non_owner(created_ids: list[int]) -> None:
    data = _create("接口测试助理壬")
    created_ids.append(data["assistantId"])

    resp = client.put(
        f"/api/v1/assistants/{data['assistantId']}",
        headers=OTHER,
        json=_payload("接口测试助理壬"),
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "NO_PERMISSION"


def test_update_replaces_tags_fully(created_ids: list[int]) -> None:
    data = _create("接口测试助理癸")
    created_ids.append(data["assistantId"])

    client.put(
        f"/api/v1/assistants/{data['assistantId']}",
        headers=OWNER,
        json=_payload("接口测试助理癸", tags=["单标签"]),
    )
    detail = client.get(f"/api/v1/assistants/{data['assistantId']}", headers=OWNER).json()["data"]
    assert detail["tags"] == ["单标签"]


# ============================ 删除 ============================


def test_delete_impact_reports_counts() -> None:
    resp = client.get("/api/v1/assistants/1/delete-impact", headers=OWNER)
    assert resp.status_code == 200
    impact = resp.json()["data"]
    assert impact["assistantId"] == 1
    assert impact["authorizedCount"] == 0
    assert impact["pendingApplyCount"] == 0


def test_delete_soft_deletes_and_hides_from_list(created_ids: list[int]) -> None:
    data = _create("接口测试助理删除")
    assistant_id = data["assistantId"]

    resp = client.delete(f"/api/v1/assistants/{assistant_id}", headers=OWNER)
    assert resp.status_code == 200
    assert resp.json()["data"] == {"assistantId": assistant_id, "deleted": True}

    # 删除后详情 404、列表不再出现
    assert client.get(f"/api/v1/assistants/{assistant_id}", headers=OWNER).status_code == 404
    listed = client.get(
        "/api/v1/assistants", headers=OWNER, params={"scope": "mine", "pageSize": 50}
    ).json()["data"]["list"]
    assert assistant_id not in [c["assistantId"] for c in listed]

    # 名称可复用（逻辑删除后唯一索引放开）
    again = _create("接口测试助理删除")
    created_ids.append(again["assistantId"])
    assert again["assistantId"] != assistant_id


def test_delete_rejects_non_owner(created_ids: list[int]) -> None:
    data = _create("接口测试助理越权")
    created_ids.append(data["assistantId"])

    resp = client.delete(f"/api/v1/assistants/{data['assistantId']}", headers=OTHER)
    assert resp.status_code == 403
    assert resp.json()["code"] == "NO_PERMISSION"
