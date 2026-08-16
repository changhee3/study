"""애플리케이션 설정 (환경 변수 기반).

.env 파일 또는 실제 환경 변수로 주입한다. (.env.example 참고)
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # Redis 연결 URL. 비어 있으면 인메모리 백엔드로 자동 폴백한다.
    redis_url: str | None = os.getenv("REDIS_URL") or None

    # 기본 Rate Limit 정책 (Token Bucket)
    default_requests: int = _get_int("RATE_LIMIT_REQUESTS", 100)
    default_window: int = _get_int("RATE_LIMIT_WINDOW", 60)
    # burst=0 이면 requests 값과 동일하게 취급 (아래 default_burst_effective 참고)
    default_burst: int = _get_int("RATE_LIMIT_BURST", 0)

    # 장애 시 정책: True면 통과(fail-open), False면 차단(fail-close)
    fail_open: bool = _get_bool("FAIL_OPEN", True)

    # 알림 채널: none | slack | discord | telegram
    notify_channel: str = (os.getenv("NOTIFY_CHANNEL", "none") or "none").lower()
    notify_webhook_url: str | None = os.getenv("NOTIFY_WEBHOOK_URL") or None
    telegram_bot_token: str | None = os.getenv("TELEGRAM_BOT_TOKEN") or None
    telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID") or None
    # 동일 이벤트 중복 알림 방지용 쿨다운(초)
    notify_cooldown: int = _get_int("NOTIFY_COOLDOWN", 300)

    @property
    def default_burst_effective(self) -> int:
        return self.default_burst or self.default_requests


settings = Settings()
