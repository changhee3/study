"""Rate Limiter — Token Bucket 알고리즘.

두 가지 백엔드를 제공한다.
  - InMemoryTokenBucket : 단일 프로세스용 (Redis 미사용 시 폴백)
  - RedisTokenBucket    : Redis Lua 스크립트로 원자적 처리 (분산 환경)

build_limiter()가 설정에 따라 적절한 백엔드를 생성하며, Redis 연결
실패 시 자동으로 인메모리로 폴백한다.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from .models import PolicyModel

logger = logging.getLogger("ratelimiter.limiter")


@dataclass
class LimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_after: float  # 버킷이 가득 차기까지 남은 초
    retry_after: float  # 다음 요청까지 대기 권장 초 (허용 시 0)


class RateLimitExceeded(Exception):
    """제한 초과 시 발생. main의 예외 핸들러가 429로 변환한다."""

    def __init__(self, result: "LimitResult", client_id: str) -> None:
        self.result = result
        self.client_id = client_id
        super().__init__(f"rate limit exceeded for {client_id}")


def _derive(allowed: bool, tokens: float, policy: PolicyModel, cost: int) -> LimitResult:
    refill = policy.refill_rate
    capacity = policy.capacity
    remaining = int(tokens)
    reset_after = (capacity - tokens) / refill if refill > 0 else 0.0
    if allowed:
        retry_after = 0.0
    else:
        retry_after = (cost - tokens) / refill if refill > 0 else 0.0
    return LimitResult(allowed, capacity, remaining, reset_after, retry_after)


class RateLimiter:
    """Rate Limiter 인터페이스."""

    async def check(self, key: str, policy: PolicyModel, cost: int = 1) -> LimitResult:
        raise NotImplementedError

    async def peek(self, key: str, policy: PolicyModel) -> LimitResult:
        """토큰 소비 없이 현재 잔여량만 조회 (cost=0)."""
        return await self.check(key, policy, cost=0)

    async def close(self) -> None:  # pragma: no cover
        pass


class InMemoryTokenBucket(RateLimiter):
    def __init__(self) -> None:
        # key -> (tokens, last_monotonic_ts)
        self._state: dict[str, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str, policy: PolicyModel, cost: int = 1) -> LimitResult:
        capacity = policy.capacity
        refill = policy.refill_rate
        now = time.monotonic()
        async with self._lock:
            tokens, last = self._state.get(key, (float(capacity), now))
            tokens = min(capacity, tokens + (now - last) * refill)
            allowed = tokens >= cost
            if allowed:
                tokens -= cost
            self._state[key] = (tokens, now)
        return _derive(allowed, tokens, policy, cost)


# 원자적 토큰 버킷 (KEYS[1]=버킷 키, ARGV=capacity, refill, now, cost)
_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil then
  tokens = capacity
  ts = now
end
local delta = math.max(0, now - ts)
tokens = math.min(capacity, tokens + delta * refill)
local allowed = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
end
redis.call('HSET', key, 'tokens', tokens, 'ts', now)
local ttl = math.ceil(capacity / refill) + 1
redis.call('EXPIRE', key, ttl)
return {allowed, tostring(tokens)}
"""


class RedisTokenBucket(RateLimiter):
    def __init__(self, client) -> None:  # client: redis.asyncio.Redis
        self._redis = client
        self._script = client.register_script(_TOKEN_BUCKET_LUA)

    async def check(self, key: str, policy: PolicyModel, cost: int = 1) -> LimitResult:
        now = time.time()
        allowed_raw, tokens_raw = await self._script(
            keys=[f"rl:{key}"],
            args=[policy.capacity, policy.refill_rate, now, cost],
        )
        tokens = float(tokens_raw)
        allowed = int(allowed_raw) == 1
        return _derive(allowed, tokens, policy, cost)

    async def close(self) -> None:
        await self._redis.aclose()


async def build_limiter(redis_url: str | None) -> RateLimiter:
    """설정에 따라 백엔드를 생성. Redis 실패 시 인메모리로 폴백한다."""
    if not redis_url:
        return InMemoryTokenBucket()
    try:
        import redis.asyncio as aioredis  # 지연 임포트 (redis 미설치 환경 대비)

        client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        await client.ping()
        logger.info("Redis 백엔드 연결 성공: %s", redis_url)
        return RedisTokenBucket(client)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis 연결 실패(%s) — 인메모리 백엔드로 폴백합니다.", exc)
        return InMemoryTokenBucket()
