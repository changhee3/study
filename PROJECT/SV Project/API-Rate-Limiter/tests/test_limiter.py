"""Token Bucket 핵심 로직 단위 테스트.

pytest-asyncio 의존성을 피하기 위해 async 코루틴은 asyncio.run()으로 감싸 실행한다.
"""
from __future__ import annotations

import asyncio
import time

from app.limiter import InMemoryTokenBucket, _derive
from app.models import PolicyModel


def run(coro):
    return asyncio.run(coro)


# ── PolicyModel 파생 값 ──────────────────────────────────────────────
def test_policy_capacity_defaults_to_requests():
    p = PolicyModel(requests=100, window_seconds=60, burst=0)
    assert p.capacity == 100  # burst=0 → requests
    assert p.refill_rate == 100 / 60


def test_policy_capacity_uses_burst_when_set():
    p = PolicyModel(requests=1000, window_seconds=60, burst=1200)
    assert p.capacity == 1200
    assert p.refill_rate == 1000 / 60


# ── _derive: allowed/remaining/retry_after 계산 ──────────────────────
def test_derive_blocked_sets_positive_retry_after():
    p = PolicyModel(requests=3, window_seconds=3, burst=3)  # refill 1 token/s
    r = _derive(allowed=False, tokens=0.0, policy=p, cost=1)
    assert r.allowed is False
    assert r.remaining == 0
    assert r.retry_after == 1.0  # (cost - tokens) / refill = 1 / 1

    r_ok = _derive(allowed=True, tokens=2.0, policy=p, cost=1)
    assert r_ok.retry_after == 0.0  # 허용 시 항상 0


# ── InMemoryTokenBucket: 허용 → 소진 → 차단 ─────────────────────────
def test_bucket_allows_up_to_capacity_then_blocks():
    p = PolicyModel(requests=3, window_seconds=60, burst=3)  # 리필 매우 느림
    bucket = InMemoryTokenBucket()
    key = "client:endpoint"

    results = [run(bucket.check(key, p)) for _ in range(3)]
    assert all(r.allowed for r in results)
    assert results[0].remaining == 2
    assert results[1].remaining == 1
    assert results[2].remaining == 0

    blocked = run(bucket.check(key, p))
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.retry_after > 0
    assert blocked.limit == 3


# ── 시간 경과 시 토큰 리필 ───────────────────────────────────────────
def test_bucket_refills_over_time():
    # capacity 3, window 1s → refill 3 tokens/s. 0.5s면 1개 이상 회복.
    p = PolicyModel(requests=3, window_seconds=1, burst=3)
    bucket = InMemoryTokenBucket()
    key = "client:endpoint"

    for _ in range(3):
        run(bucket.check(key, p))
    assert run(bucket.check(key, p)).allowed is False  # 소진 직후 차단

    time.sleep(0.5)
    assert run(bucket.check(key, p)).allowed is True  # 리필 후 재허용


# ── peek(cost=0): 소비 없이 조회 ────────────────────────────────────
def test_peek_does_not_consume_tokens():
    p = PolicyModel(requests=10, window_seconds=60, burst=10)
    bucket = InMemoryTokenBucket()

    first = run(bucket.peek("k:ep", p))
    second = run(bucket.peek("k:ep", p))
    assert first.allowed is True
    assert first.remaining == 10
    assert second.remaining == 10  # 두 번 peek해도 그대로


# ── cost가 잔여 토큰보다 크면 차단 ──────────────────────────────────
def test_cost_greater_than_available_blocks():
    p = PolicyModel(requests=5, window_seconds=60, burst=5)
    bucket = InMemoryTokenBucket()
    r = run(bucket.check("k:ep", p, cost=6))
    assert r.allowed is False
    assert r.remaining == 5  # 소비되지 않음


# ── 서로 다른 key는 독립적인 버킷 ───────────────────────────────────
def test_keys_are_isolated():
    p = PolicyModel(requests=1, window_seconds=60, burst=1)
    bucket = InMemoryTokenBucket()
    assert run(bucket.check("a:ep", p)).allowed is True
    assert run(bucket.check("a:ep", p)).allowed is False  # a 소진
    assert run(bucket.check("b:ep", p)).allowed is True  # b는 영향 없음
