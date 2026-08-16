"""API 라우터 및 재사용 가능한 rate limit 의존성.

엔드포인트 (명세서 8절 기준):
  POST /v1/check              요청 허용 여부 판정
  GET  /v1/usage/{client_id}  사용량/잔여량 조회
  GET  /v1/policies           정책 목록 조회
  PUT  /v1/policies           정책 등록/수정
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from .config import settings
from .identify import identify_client
from .limiter import LimitResult, RateLimiter, RateLimitExceeded
from .models import (
    CheckRequest,
    CheckResponse,
    PolicyModel,
    PolicyUpsert,
    UsageResponse,
)
from .notifier import Notifier
from .policies import policy_store

logger = logging.getLogger("ratelimiter.api")

router = APIRouter(prefix="/v1", tags=["요청 제한"])


def get_limiter(request: Request) -> RateLimiter:
    return request.app.state.limiter


def get_notifier(request: Request) -> Notifier:
    return request.app.state.notifier


async def _evaluate(
    request: Request,
    explicit_id: str | None,
    endpoint: str,
    cost: int,
    limiter: RateLimiter,
    notifier: Notifier | None,
) -> tuple[str, str, LimitResult]:
    """식별 → 정책 조회 → 제한 검사 → (초과 시) 알림."""
    client_id, plan = identify_client(request, explicit_id)
    policy = policy_store.get(plan)

    try:
        result = await limiter.check(f"{client_id}:{endpoint}", policy, cost=cost)
    except Exception as exc:  # noqa: BLE001 — 백엔드 장애 시 fail-open/close 정책 적용
        logger.warning("limiter 백엔드 오류(%s) — fail_open=%s", exc, settings.fail_open)
        if settings.fail_open:
            return client_id, plan, LimitResult(True, policy.capacity, policy.capacity, 0.0, 0.0)
        return client_id, plan, LimitResult(False, policy.capacity, 0, 0.0, 1.0)

    if not result.allowed and notifier is not None:
        await notifier.notify(
            event_key=f"exceed:{client_id}",
            title="Rate limit 초과 감지",
            fields={
                "client": client_id,
                "plan": plan,
                "endpoint": endpoint,
                "limit": result.limit,
                "retry_after(s)": round(result.retry_after, 2),
            },
            severity="warning",
        )
    return client_id, plan, result


@router.post(
    "/check",
    response_model=CheckResponse,
    summary="요청 허용 여부 판정",
    responses={
        200: {"description": "판정 완료 (allowed / remaining / retry_after 반환)"},
        422: {"description": "요청 형식 오류 (예: cost가 1 미만)"},
    },
)
async def check(
    body: CheckRequest,
    request: Request,
    limiter: RateLimiter = Depends(get_limiter),
    notifier: Notifier = Depends(get_notifier),
) -> CheckResponse:
    client_id, _plan, result = await _evaluate(
        request, body.client_id, body.endpoint, body.cost, limiter, notifier
    )
    return CheckResponse(
        allowed=result.allowed,
        client_id=client_id,
        limit=result.limit,
        remaining=result.remaining,
        reset_after=round(result.reset_after, 3),
        retry_after=round(result.retry_after, 3),
    )


@router.get(
    "/usage/{client_id}",
    response_model=UsageResponse,
    summary="사용량/잔여량 조회",
    responses={
        200: {"description": "조회 완료 (토큰 소비 없음)"},
        422: {"description": "요청 형식 오류"},
    },
)
async def usage(
    client_id: str,
    request: Request,
    endpoint: str = "default",
    limiter: RateLimiter = Depends(get_limiter),
) -> UsageResponse:
    _cid, plan = identify_client(request, client_id)
    policy = policy_store.get(plan)
    result = await limiter.peek(f"{client_id}:{endpoint}", policy)
    return UsageResponse(
        client_id=client_id,
        limit=result.limit,
        remaining=result.remaining,
        reset_after=round(result.reset_after, 3),
    )


@router.get(
    "/policies",
    response_model=dict[str, PolicyModel],
    summary="정책 목록 조회",
    responses={200: {"description": "요금제별 정책 목록"}},
)
async def list_policies() -> dict[str, PolicyModel]:
    return policy_store.all()


@router.put(
    "/policies",
    summary="정책 등록/수정",
    responses={
        200: {"description": "등록/수정 완료"},
        422: {"description": "요청 형식 오류"},
    },
)
async def upsert_policy(body: PolicyUpsert) -> dict[str, str]:
    policy_store.upsert(body.plan, body.policy)
    return {"status": "ok", "plan": body.plan}


def rate_limit(endpoint: str = "default", cost: int = 1):
    """임의의 라우트를 보호하는 의존성 팩토리.

    사용 예:
        @app.get("/demo")
        async def demo(_=Depends(rate_limit(endpoint="demo"))):
            ...
    제한 초과 시 RateLimitExceeded를 던지고, main의 핸들러가 429로 변환한다.
    """

    async def dependency(request: Request) -> LimitResult:
        limiter: RateLimiter = request.app.state.limiter
        notifier: Notifier = request.app.state.notifier
        _cid, _plan, result = await _evaluate(request, None, endpoint, cost, limiter, notifier)
        if not result.allowed:
            raise RateLimitExceeded(result, _cid)
        return result

    return dependency
