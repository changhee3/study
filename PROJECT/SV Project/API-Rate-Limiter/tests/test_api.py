"""HTTP 엔드포인트 통합 테스트 (FastAPI TestClient).

TestClient를 `with` 컨텍스트로 사용해 lifespan(startup)을 실행 → app.state에
InMemoryTokenBucket 백엔드와 Notifier가 세팅된다. (REDIS_URL 미설정 → 인메모리)

주의: policy_store는 모듈 전역 싱글턴이라 PUT 테스트가 상태를 오염시킨다.
매 테스트마다 스냅샷 후 복원해 격리한다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main
from app.policies import policy_store


@pytest.fixture()
def client():
    # with 컨텍스트가 lifespan을 돌려 매 테스트마다 새 limiter(빈 버킷)를 만든다.
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(autouse=True)
def restore_policies():
    snapshot = policy_store.all()  # dict 사본
    yield
    policy_store._policies = snapshot  # PUT으로 바뀐 정책 원복


def test_health_reports_inmemory_backend(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["backend"] == "InMemoryTokenBucket"


def test_list_policies_contains_defaults(client):
    data = client.get("/v1/policies").json()
    assert {"free", "pro", "enterprise"} <= set(data)
    assert data["pro"]["burst"] == 1200
    assert data["enterprise"]["requests"] == 10000


def test_upsert_policy_adds_new_plan(client):
    payload = {"plan": "gold", "policy": {"requests": 5, "window_seconds": 10, "burst": 8}}
    r = client.put("/v1/policies", json=payload)
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "plan": "gold"}

    data = client.get("/v1/policies").json()
    assert data["gold"]["burst"] == 8


def test_check_with_pro_key_consumes_one_token(client):
    r = client.post(
        "/v1/check", headers={"X-API-Key": "demo-pro-key"}, json={"endpoint": "search"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is True
    assert body["client_id"] == "key:demo-pro-key"
    assert body["limit"] == 1200
    assert body["remaining"] == 1199  # 1개 소비


def test_usage_peek_does_not_consume(client):
    first = client.get("/v1/usage/tenant-x").json()
    second = client.get("/v1/usage/tenant-x").json()
    assert first["remaining"] == second["remaining"]  # peek → 소비 없음
    assert first["limit"] == first["remaining"]  # 처음엔 가득 참


def test_demo_returns_429_with_headers_after_limit(client):
    # 기본 free 정책(100)은 429까지 100회 필요 → 테스트용으로 free를 축소.
    client.put(
        "/v1/policies",
        json={"plan": "free", "policy": {"requests": 2, "window_seconds": 60, "burst": 2}},
    )
    assert client.get("/demo").status_code == 200
    assert client.get("/demo").status_code == 200

    blocked = client.get("/demo")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert blocked.headers["X-RateLimit-Limit"] == "2"
    assert blocked.headers["X-RateLimit-Remaining"] == "0"

    body = blocked.json()
    assert body["error"] == "rate_limit_exceeded"
    assert body["client_id"] == "ip:testclient"  # TestClient 기본 호스트


def test_check_validation_rejects_zero_cost(client):
    # cost는 ge=1 → 0이면 422
    r = client.post("/v1/check", json={"endpoint": "x", "cost": 0})
    assert r.status_code == 422
