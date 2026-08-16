"""클라이언트 식별 로직(identify_client) 단위 테스트.

identify_client는 request.headers.get(...)과 request.client.host만 사용하므로
가벼운 SimpleNamespace 가짜 요청으로 충분히 검증할 수 있다.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.identify import identify_client


def make_req(headers: dict | None = None, host: str | None = "1.2.3.4"):
    return SimpleNamespace(
        headers=headers or {},
        client=SimpleNamespace(host=host) if host is not None else None,
    )


def test_known_api_key_maps_to_plan():
    cid, plan = identify_client(make_req({"X-API-Key": "demo-pro-key"}))
    assert plan == "pro"
    assert cid == "key:demo-pro-key"


def test_unknown_api_key_falls_back_to_ip_free():
    cid, plan = identify_client(make_req({"X-API-Key": "nope"}, host="9.9.9.9"))
    assert plan == "free"
    assert cid == "ip:9.9.9.9"


def test_no_key_uses_source_ip():
    cid, plan = identify_client(make_req(host="5.5.5.5"))
    assert (cid, plan) == ("ip:5.5.5.5", "free")


def test_missing_client_host_becomes_unknown():
    cid, plan = identify_client(make_req(host=None))
    assert cid == "ip:unknown"
    assert plan == "free"


def test_explicit_id_overrides_but_keeps_plan():
    cid, plan = identify_client(
        make_req({"X-API-Key": "demo-enterprise-key"}), explicit_id="tenant-42"
    )
    assert cid == "tenant-42"
    assert plan == "enterprise"
