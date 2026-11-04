"""Unit tests for notification dispatcher and batching."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

from home_notifications.config import AppConfig, FeatureConfig, SystemConfig, TelegramConfig
from home_notifications.notifier import NotificationDispatcher
from home_notifications.state import StateManager


@pytest.fixture
def mock_app_setup(tmp_path: Path):
    telegram_cfg = TelegramConfig(bot_token="test-token", chat_id=123456)
    system_cfg = SystemConfig(state_file=str(tmp_path / "state.json"))
    features = {
        "batched_feat": FeatureConfig(
            name="batched_feat",
            enabled=True,
            interval_seconds=60,
            notify_mode="batched",
            batch_interval_seconds=60,
        ),
        "immediate_feat": FeatureConfig(
            name="immediate_feat",
            enabled=True,
            interval_seconds=60,
            notify_mode="immediate",
            batch_interval_seconds=60,
        ),
    }
    config = AppConfig(
        base_dir=tmp_path,
        telegram=telegram_cfg,
        system=system_cfg,
        features=features,
        devices={},
    )
    state = StateManager(tmp_path / "state.json")
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=True)

    dispatcher = NotificationDispatcher(mock_bot, config, state)
    return dispatcher, mock_bot, state


@pytest.mark.asyncio
async def test_immediate_vs_batched_dispatch(mock_app_setup):
    dispatcher, mock_bot, state = mock_app_setup

    # 1. Immediate feature
    await dispatcher.notify(
        category="immediate_feat",
        title="Immediate Alert",
        message="Notice immediately",
        level="WARNING",
    )
    mock_bot.send_message.assert_called_once()
    assert len(state.data.get("queued_notifications", [])) == 0

    # 2. Batched feature
    mock_bot.send_message.reset_mock()
    await dispatcher.notify(
        category="batched_feat",
        title="Batch Item 1",
        message="Queued for later",
        level="INFO",
    )
    # Shouldn't send immediately
    mock_bot.send_message.assert_not_called()
    assert len(state.data.get("queued_notifications", [])) == 1

    # 3. Flush batches
    sent_count = await dispatcher.flush_batches()
    assert sent_count == 1
    mock_bot.send_message.assert_called_once()
    assert len(state.data.get("queued_notifications", [])) == 0


@pytest.mark.asyncio
async def test_telegram_pause_and_disable(mock_app_setup):
    dispatcher, mock_bot, state = mock_app_setup

    # 1. Test Pause
    dispatcher.pause(seconds=3600)
    assert dispatcher.is_paused() is True
    assert dispatcher.get_pause_remaining() > 0

    mock_bot.send_message.reset_mock()
    sent = await dispatcher.send_immediate("system", "Test", "Msg")
    assert sent is False
    mock_bot.send_message.assert_not_called()

    # 2. Test Resume
    dispatcher.resume()
    assert dispatcher.is_paused() is False

    sent = await dispatcher.send_immediate("system", "Test", "Msg")
    assert sent is True
    mock_bot.send_message.assert_called_once()

    # 3. Test Global Disable
    dispatcher.config.telegram.enabled = False
    mock_bot.send_message.reset_mock()
    sent = await dispatcher.send_immediate("system", "Test", "Msg")
    assert sent is False
    mock_bot.send_message.assert_not_called()

