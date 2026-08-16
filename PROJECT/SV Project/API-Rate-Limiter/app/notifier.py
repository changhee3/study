"""알림(Notification) 연동.

이벤트 발생 시 메신저 채널(Slack/Discord/Telegram)의 Webhook으로 알림을
전송한다. 별도 앱 없이 백엔드에서 httpx로 비동기 POST 한 번으로 처리한다.

  - 쿨다운으로 동일 이벤트의 중복 알림을 방지 (디바운스)
  - 전송 실패는 서비스 흐름을 막지 않도록 삼켜서 로깅만 한다
"""
from __future__ import annotations

import logging
import time
from typing import Any

from .config import Settings

logger = logging.getLogger("ratelimiter.notifier")


class Notifier:
    def __init__(self, settings: Settings) -> None:
        self._channel = settings.notify_channel
        self._webhook_url = settings.notify_webhook_url
        self._tg_token = settings.telegram_bot_token
        self._tg_chat = settings.telegram_chat_id
        self._cooldown = settings.notify_cooldown
        self._last_sent: dict[str, float] = {}  # event_key -> last monotonic ts

    @property
    def enabled(self) -> bool:
        if self._channel == "telegram":
            return bool(self._tg_token and self._tg_chat)
        if self._channel in {"slack", "discord"}:
            return bool(self._webhook_url)
        return False

    async def notify(
        self,
        event_key: str,
        title: str,
        fields: dict[str, Any],
        severity: str = "warning",
    ) -> bool:
        """알림 전송. 쿨다운 내 동일 event_key면 skip하고 False 반환."""
        if not self.enabled:
            return False

        now = time.monotonic()
        last = self._last_sent.get(event_key)
        if last is not None and (now - last) < self._cooldown:
            return False
        self._last_sent[event_key] = now

        try:
            await self._send(title, fields, severity)
            return True
        except Exception as exc:  # noqa: BLE001
            # 실패 시 재시도/로컬 백업 로직을 여기에 확장한다 (스켈레톤은 로깅만).
            logger.warning("알림 전송 실패: %s", exc)
            return False

    async def _send(self, title: str, fields: dict[str, Any], severity: str) -> None:
        import httpx  # 지연 임포트 (httpx 미설치 환경 대비)

        lines = [f"[{severity.upper()}] {title}"]
        lines += [f"- {k}: {v}" for k, v in fields.items()]
        text = "\n".join(lines)

        async with httpx.AsyncClient(timeout=5.0) as http:
            if self._channel == "slack":
                await http.post(self._webhook_url, json={"text": text})
            elif self._channel == "discord":
                await http.post(self._webhook_url, json={"content": text})
            elif self._channel == "telegram":
                url = f"https://api.telegram.org/bot{self._tg_token}/sendMessage"
                await http.post(url, json={"chat_id": self._tg_chat, "text": text})
