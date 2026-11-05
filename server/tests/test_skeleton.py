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
