"""
Tests for pipeline/scheduler.py — DataScheduler background sync engine.
"""
import threading
import time
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

from pipeline.scheduler import (
    DataScheduler, SchedulerConfig, SchedulerEvent,
    SchedulerStatus, TaskType, WIB,
    IDX_OPEN_HOUR, IDX_CLOSE_HOUR, IDX_TRADING_DAYS,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def scheduler():
    """Create scheduler with short intervals for testing."""
    config = SchedulerConfig(
        daily_fetch_interval_minutes=1,
        intraday_interval_minutes=1,
        auto_clean=True,
        universe="lq45",
        respect_trading_hours=False,  # Disable for testing
    )
    return DataScheduler(config=config)


@pytest.fixture
def strict_scheduler():
    """Scheduler that respects trading hours."""
    config = SchedulerConfig(respect_trading_hours=True)
    return DataScheduler(config=config)


# ------------------------------------------------------------------
# Test: Trading Hours Logic
# ------------------------------------------------------------------

class TestTradingHours:
    def test_weekday_during_hours(self):
        """Monday 10:30 WIB = trading hours."""
        # Monday 10:30 WIB
        dt = datetime(2026, 8, 10, 10, 30, tzinfo=WIB)
        assert DataScheduler._is_trading_hours(dt) is True

    def test_weekday_before_open(self):
        """Monday 08:00 WIB = before open."""
        dt = datetime(2026, 8, 10, 8, 0, tzinfo=WIB)
        assert DataScheduler._is_trading_hours(dt) is False

    def test_weekday_after_close(self):
        """Monday 16:30 WIB = after close."""
        dt = datetime(2026, 8, 10, 16, 30, tzinfo=WIB)
        assert DataScheduler._is_trading_hours(dt) is False

    def test_weekend(self):
        """Saturday 11:00 WIB = weekend, not trading."""
        dt = datetime(2026, 8, 15, 11, 0, tzinfo=WIB)
        assert DataScheduler._is_trading_hours(dt) is False

    def test_friday_boundary(self):
        """Friday 15:59 = still trading."""
        dt = datetime(2026, 8, 14, 15, 59, tzinfo=WIB)
        assert DataScheduler._is_trading_hours(dt) is True

    def test_next_trading_window_weekend(self):
        """Saturday should return Monday 09:00."""
        dt = datetime(2026, 8, 15, 12, 0, tzinfo=WIB)
        nxt = DataScheduler.next_trading_window(dt)
        assert nxt.weekday() == 0  # Monday
        assert nxt.hour == IDX_OPEN_HOUR

    def test_next_trading_window_after_close(self):
        """Monday 17:00 should return Tuesday 09:00."""
        dt = datetime(2026, 8, 10, 17, 0, tzinfo=WIB)
        nxt = DataScheduler.next_trading_window(dt)
        assert nxt.weekday() == 1  # Tuesday
        assert nxt.hour == IDX_OPEN_HOUR

    def test_next_trading_window_during_hours(self):
        """Monday 11:00 should return same time (already in window)."""
        dt = datetime(2026, 8, 10, 11, 0, tzinfo=WIB)
        nxt = DataScheduler.next_trading_window(dt)
        assert nxt == dt


# ------------------------------------------------------------------
# Test: Scheduler Lifecycle
# ------------------------------------------------------------------

class TestSchedulerLifecycle:
    def test_init_state(self, scheduler):
        assert scheduler.status == SchedulerStatus.IDLE
        assert scheduler.is_running() is False
        assert scheduler._run_count == 0

    def test_start_and_stop(self, scheduler):
        scheduler.start_background()
        assert scheduler.status == SchedulerStatus.RUNNING
        assert scheduler.is_running() is True

        scheduler.stop()
        assert scheduler.status == SchedulerStatus.STOPPED
        assert scheduler.is_running() is False

    def test_double_start_ignored(self, scheduler):
        scheduler.start_background()
        scheduler.start_background()  # should be no-op
        assert scheduler.status == SchedulerStatus.RUNNING
        scheduler.stop()

    def test_repr(self, scheduler):
        r = repr(scheduler)
        assert "DataScheduler" in r
        assert "idle" in r

    def test_get_status_summary(self, scheduler):
        summary = scheduler.get_status_summary()
        assert "status" in summary
        assert "is_trading_hours" in summary
        assert "current_time_wib" in summary
        assert "total_runs" in summary


# ------------------------------------------------------------------
# Test: Event System
# ------------------------------------------------------------------

class TestSchedulerEvents:
    def test_event_callback_fired(self):
        events = []

        def on_event(ev):
            events.append(ev)

        config = SchedulerConfig(respect_trading_hours=False)
        sched = DataScheduler(config=config, on_event=on_event)
        sched._emit("test_task", "started", "Testing event emission")

        assert len(events) == 1
        assert events[0].task == "test_task"
        assert events[0].status == "started"

    def test_history_capped_at_100(self, scheduler):
        for i in range(120):
            scheduler._emit("bulk", "started", f"Event {i}")
        assert len(scheduler._history) == 100

    def test_get_history(self, scheduler):
        scheduler._emit("t1", "completed", "Done")
        history = scheduler.get_history()
        assert len(history) == 1
        assert history[0].message == "Done"


# ------------------------------------------------------------------
# Test: Scheduler Config
# ------------------------------------------------------------------

class TestSchedulerConfig:
    def test_default_config(self):
        c = SchedulerConfig()
        assert c.daily_fetch_interval_minutes == 60
        assert c.intraday_interval_minutes == 15
        assert c.auto_clean is True
        assert c.universe == "lq45"
        assert c.respect_trading_hours is True
        assert c.max_retries == 3

    def test_custom_config(self):
        c = SchedulerConfig(
            daily_fetch_interval_minutes=30,
            intraday_interval_minutes=5,
            universe="kompas100",
        )
        assert c.daily_fetch_interval_minutes == 30
        assert c.universe == "kompas100"


# ------------------------------------------------------------------
# Test: Run Once (with mocked IO)
# ------------------------------------------------------------------

class TestRunOnce:
    def test_run_once_skipped_outside_hours(self, strict_scheduler):
        """Scheduler respects trading hours when not forced."""
        # Patch _is_trading_hours to return False
        with patch.object(DataScheduler, '_is_trading_hours', return_value=False):
            result = strict_scheduler.run_once(force=False)
            assert result.get("skipped") is True
            assert "jam bursa" in result["reason"]

    def test_run_once_forced(self, strict_scheduler):
        """Force mode bypasses trading hours."""
        with patch.object(strict_scheduler, '_do_daily_fetch',
                          return_value={"task": "daily_fetch", "status": "completed"}):
            with patch.object(strict_scheduler, '_do_intraday_fetch',
                              return_value={"task": "intraday_fetch", "status": "completed"}):
                with patch.object(strict_scheduler, '_do_data_clean',
                                  return_value={"task": "data_clean", "status": "completed"}):
                    result = strict_scheduler.run_once(force=True)
                    assert result.get("skipped") is None
                    assert len(result["tasks"]) == 3


# ------------------------------------------------------------------
# Test: Interval Checks
# ------------------------------------------------------------------

class TestIntervalChecks:
    def test_should_run_daily_first_time(self, scheduler):
        now = datetime.now(WIB)
        assert scheduler._should_run_daily(now) is True

    def test_should_run_daily_after_interval(self, scheduler):
        scheduler._last_daily_fetch = datetime(2026, 1, 1, 10, 0, tzinfo=WIB)
        now = datetime(2026, 1, 1, 11, 30, tzinfo=WIB)
        assert scheduler._should_run_daily(now) is True

    def test_should_not_run_daily_before_interval(self, scheduler):
        now = datetime.now(WIB)
        scheduler._last_daily_fetch = now
        assert scheduler._should_run_daily(now) is False

    def test_should_run_intraday_first_time(self, scheduler):
        now = datetime.now(WIB)
        assert scheduler._should_run_intraday(now) is True
