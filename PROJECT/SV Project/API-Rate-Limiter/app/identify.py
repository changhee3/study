"""클라이언트 식별 로직.

우선순위: 명시적 client_id > X-API-Key 헤더 > 소스 IP
반환값: (client_id, plan)
"""
from __future__ import annotations

from fastapi import Request

# 데모용 API Key -> 요금제 매핑. 실제로는 DB/Redis에서 조회한다.
API_KEYS: dict[str, str] = {
    "demo-free-key": "free",
    "demo-pro-key": "pro",
    "demo-enterprise-key": "enterprise",
}


def identify_client(request: Request, explicit_id: str | None = None) -> tuple[str, str]:
    api_key = request.headers.get("X-API-Key")
    if api_key and api_key in API_KEYS:
        plan = API_KEYS[api_key]
        return (explicit_id or f"key:{api_key}", plan)

    # API Key가 없으면 IP로 폴백 (free 정책 적용)
    client_host = request.client.host if request.client else "unknown"
    return (explicit_id or f"ip:{client_host}", "free")
