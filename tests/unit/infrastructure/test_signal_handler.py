"""Characterization + regression tests for AsyncSignalHandler.

Safety net for consolidating the daemon's signal handling. The handler logic is
exercised directly (no real OS signal handlers are installed), including C5:
recurring reload signals must stay deliverable after the event is cleared.
"""

import asyncio
import signal
import sys

import pytest

from localport.infrastructure.shutdown.signal_handler import (
    AsyncSignalHandler,
    SignalType,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="Exercises Unix signal semantics"
)


async def _drain() -> None:
    """Let the fire-and-forget task the handler schedules run to completion."""
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_shutdown_signal_sets_event():
    handler = AsyncSignalHandler()
    handler._async_signal_handler(signal.SIGTERM, SignalType.SHUTDOWN)
    await _drain()
    assert handler.is_shutdown_requested()


@pytest.mark.asyncio
async def test_shutdown_signal_is_deduplicated():
    handler = AsyncSignalHandler()
    handler._async_signal_handler(signal.SIGTERM, SignalType.SHUTDOWN)
    await _drain()
    # A repeated shutdown signal must not error and must stay shut down.
    handler._async_signal_handler(signal.SIGTERM, SignalType.SHUTDOWN)
    await _drain()
    assert handler.is_shutdown_requested()


@pytest.mark.asyncio
async def test_reload_signal_sets_event():
    handler = AsyncSignalHandler()
    handler._async_signal_handler(signal.SIGUSR1, SignalType.RELOAD)
    await _drain()
    assert handler.reload_event.is_set()


@pytest.mark.asyncio
async def test_recurring_reload_is_redeliverable():
    """C5 regression: a second reload after clearing the event must be delivered."""
    handler = AsyncSignalHandler()

    handler._async_signal_handler(signal.SIGUSR1, SignalType.RELOAD)
    await _drain()
    assert handler.reload_event.is_set()

    # The daemon clears the event after handling each reload.
    handler.reload_event.clear()

    # A subsequent reload must set the event again. Previously the permanent
    # dedup set dropped every reload after the first.
    handler._async_signal_handler(signal.SIGUSR1, SignalType.RELOAD)
    await _drain()
    assert handler.reload_event.is_set()


@pytest.mark.asyncio
async def test_reset_events_clears_state():
    handler = AsyncSignalHandler()
    handler._async_signal_handler(signal.SIGTERM, SignalType.SHUTDOWN)
    await _drain()
    assert handler.is_shutdown_requested()

    handler.reset_events()
    assert not handler.is_shutdown_requested()
    assert not handler.reload_event.is_set()
