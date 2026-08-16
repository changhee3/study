"""Notifier(웹훅 알림) 단위 테스트.

실제 네트워크 전송(_send)은 가짜 코루틴으로 대체하여 enabled 판정과
쿨다운(디바운스), 실패 흡수만 검증한다.
"""
from __future__ import annotations

import asyncio
import dataclasses

from app.config import settings
from app.notifier import Notifier


def run(coro):
    return asyncio.run(coro)


def _settings(**overrides):
    """기본 settings에서 일부 필드만 바꾼 frozen dataclass 사본."""
    return dataclasses.replace(settings, **overrides)


def test_disabled_when_channel_none():
    n = Notifier(_settings(notify_channel="none"))
    assert n.enabled is False
    assert run(n.notify("e", "t", {})) is False  # 비활성 시 항상 False


def test_slack_requires_webhook_url():
    assert Notifier(_settings(notify_channel="slack", notify_webhook_url=None)).enabled is False
    assert Notifier(_settings(notify_channel="slack", notify_webhook_url="http://x")).enabled is True


def test_telegram_requires_token_and_chat():
    assert Notifier(
        _settings(notify_channel="telegram", telegram_bot_token="t", telegram_chat_id=None)
    ).enabled is False
    assert Notifier(
        _settings(notify_channel="telegram", telegram_bot_token="t", telegram_chat_id="c")
    ).enabled is True


def test_cooldown_debounces_same_event_key():
    n = Notifier(
        _settings(notify_channel="slack", notify_webhook_url="http://x", notify_cooldown=300)
    )
    sent: list[str] = []

    async def fake_send(title, fields, severity):
        sent.append(title)

    n._send = fake_send  # 네트워크 전송 대체

    assert run(n.notify("exceed:c1", "first", {})) is True
    assert run(n.notify("exceed:c1", "dup", {})) is False  # 쿨다운 내 동일 키 → skip
    assert run(n.notify("exceed:c2", "other", {})) is True  # 다른 키 → 전송
    assert sent == ["first", "other"]


def test_send_failure_is_swallowed():
    n = Notifier(_settings(notify_channel="slack", notify_webhook_url="http://x"))

    async def boom(*args, **kwargs):
        raise RuntimeError("network down")

    n._send = boom
    # 전송이 예외를 던져도 서비스 흐름을 막지 않고 False 반환
    assert run(n.notify("k", "t", {})) is False
