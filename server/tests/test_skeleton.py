"""骨架冒烟测试：应用装配、健康检查、鉴权与错误码。

运行：cd server && python -m pytest -q
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_unified_payload() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "OK"
    assert body["traceId"]


def test_health_reports_database_status() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] in {"ok", "degraded"}
    assert body["database"] in {"up", "down"}


def test_trace_id_header_is_returned() -> None:
    resp = client.get("/health", headers={"X-Trace-Id": "fixed-trace-id"})
    assert resp.headers["X-Trace-Id"] == "fixed-trace-id"


def test_categories_requires_login() -> None:
    resp = client.get("/api/v1/categories")
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHENTICATED"


def test_categories_returns_seeded_dict() -> None:
    resp = client.get("/api/v1/categories", headers={"X-User-Id": "1001"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["code"] == "OK"
    assert isinstance(payload["data"]["list"], list)


def test_create_category_rejects_non_admin() -> None:
    resp = client.post(
        "/api/v1/categories",
        headers={"X-User-Id": "1001"},
        json={"name": "冒烟测试"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "NO_PERMISSION"


def test_create_category_rejects_overlong_name() -> None:
    resp = client.post(
        "/api/v1/categories",
        headers={"X-User-Id": "9001"},
        json={"name": "0123456789A"},
    )
    assert resp.status_code == 400
    assert resp.json()["data"]["field"] == "name"


def test_rename_category_rejects_non_admin() -> None:
    resp = client.put(
        "/api/v1/categories/2",
        headers={"X-User-Id": "1001"},
        json={"name": "人资改名"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "NO_PERMISSION"


def test_rename_category_updates_seeded_name() -> None:
    """管理员重命名分类：返回新名称，改回原名避免污染演示数据。"""
    resp = client.put(
        "/api/v1/categories/5",
        headers={"X-User-Id": "9001"},
        json={"name": "经营管理"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "经营管理"

    renamed = client.put(
        "/api/v1/categories/5",
        headers={"X-User-Id": "9001"},
        json={"name": "经营改名"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["data"]["name"] == "经营改名"

    restored = client.put(
        "/api/v1/categories/5",
        headers={"X-User-Id": "9001"},
        json={"name": "经营管理"},
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["name"] == "经营管理"


def test_rename_category_rejects_duplicate_name() -> None:
    resp = client.put(
        "/api/v1/categories/2",
        headers={"X-User-Id": "9001"},
        json={"name": "协同办公"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "CATEGORY_DUPLICATED"


def test_delete_category_rejects_when_in_use() -> None:
    """分类下存在助理时不允许删除（分类 2 = 人资，演示数据中有助理）。"""
    resp = client.delete("/api/v1/categories/2", headers={"X-User-Id": "9001"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "CATEGORY_IN_USE"
    assert resp.json()["data"]["assistantCount"] > 0


def test_delete_category_soft_deletes_empty_category() -> None:
    admin = {"X-User-Id": "9001"}
    # 可重复执行：先清掉上次残留的同名分类
    for item in client.get("/api/v1/categories", headers=admin).json()["data"]["list"]:
        if item["name"] == "临时分类":
            client.delete(f"/api/v1/categories/{item['categoryId']}", headers=admin)

    created = client.post("/api/v1/categories", headers=admin, json={"name": "临时分类"})
    assert created.status_code == 200
    category_id = created.json()["data"]["categoryId"]

    deleted = client.delete(f"/api/v1/categories/{category_id}", headers=admin)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True

    listed = client.get("/api/v1/categories", headers=admin).json()["data"]["list"]
    assert category_id not in [item["categoryId"] for item in listed]


def test_delete_category_requires_admin() -> None:
    resp = client.delete("/api/v1/categories/2", headers={"X-User-Id": "1001"})
    assert resp.status_code == 403
    assert resp.json()["code"] == "NO_PERMISSION"


def test_auth_scope_requires_admin() -> None:
    resp = client.get(
        "/api/v1/assistants",
        headers={"X-User-Id": "1001"},
        params={"scope": "auth"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "NO_PERMISSION"

