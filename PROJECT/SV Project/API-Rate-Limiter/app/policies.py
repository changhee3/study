"""요금제(plan)별 Rate Limit 정책 저장소.

스켈레톤에서는 인메모리 dict로 구현한다. 실제 환경에서는 Redis/DB에서
로드·저장하도록 교체하고, 관리 API(PUT /v1/policies)로 동적 갱신한다.
"""
from __future__ import annotations

from .config import settings
from .models import PolicyModel


class PolicyStore:
    def __init__(self) -> None:
        self._default = PolicyModel(
            requests=settings.default_requests,
            window_seconds=settings.default_window,
            burst=settings.default_burst_effective,
        )
        self._policies: dict[str, PolicyModel] = {
            "free": self._default,
            "pro": PolicyModel(requests=1000, window_seconds=60, burst=1200),
            "enterprise": PolicyModel(requests=10000, window_seconds=60, burst=15000),
        }

    def get(self, plan: str) -> PolicyModel:
        return self._policies.get(plan, self._default)

    def upsert(self, plan: str, policy: PolicyModel) -> None:
        self._policies[plan] = policy

    def all(self) -> dict[str, PolicyModel]:
        return dict(self._policies)


policy_store = PolicyStore()
