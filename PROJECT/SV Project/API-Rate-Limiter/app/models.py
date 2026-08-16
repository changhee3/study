"""요청/응답 및 정책 데이터 모델 (Pydantic)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CheckRequest(BaseModel):
    client_id: str | None = Field(
        None, description="명시적 클라이언트 식별자 (없으면 서버가 요청에서 추론)"
    )
    endpoint: str = Field("default", description="대상 엔드포인트/리소스 키")
    cost: int = Field(1, ge=1, description="이번 요청이 소비하는 토큰 수")


class CheckResponse(BaseModel):
    allowed: bool
    client_id: str
    limit: int
    remaining: int
    reset_after: float = Field(..., description="버킷이 가득 차기까지 남은 초")
    retry_after: float = Field(0, description="다음 요청까지 대기 권장 초 (허용 시 0)")


class UsageResponse(BaseModel):
    client_id: str
    limit: int
    remaining: int
    reset_after: float


class PolicyModel(BaseModel):
    """Token Bucket 파라미터로 환산되는 제한 정책."""

    requests: int = Field(..., ge=1, description="윈도우당 허용 요청 수")
    window_seconds: int = Field(..., ge=1, description="시간 창 (초)")
    burst: int = Field(0, ge=0, description="순간 버스트 허용량 (0이면 requests와 동일)")

    @property
    def capacity(self) -> int:
        """버킷 용량 = 최대로 몰아 쓸 수 있는 토큰 수."""
        return self.burst or self.requests

    @property
    def refill_rate(self) -> float:
        """초당 토큰 충전 속도."""
        return self.requests / self.window_seconds


class PolicyUpsert(BaseModel):
    plan: str = Field(..., description="요금제/정책 이름 (free, pro, enterprise ...)")
    policy: PolicyModel
