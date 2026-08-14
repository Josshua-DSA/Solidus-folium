"""
Background Data Scheduler — Automated data sync during IDX trading hours.

Menyediakan:
  - Penjadwalan otomatis fetch data harian & intraday.
  - Auto-cleaning data setelah fetch.
  - Respects jam bursa IDX (Senin-Jumat 09:00-16:00 WIB).
  - Thread-based background runner yang tidak blocking TUI/GUI.
  - Event callback untuk notifikasi ke UI layer.

Usage:
    # Standalone CLI
    python main.py scheduler start

    # Embedded di TUI
    scheduler = DataScheduler(...)
    scheduler.start_background()
"""
import threading
import time
import logging
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Timezone WIB (UTC+7)
WIB = ZoneInfo("Asia/Jakarta")

# IDX Trading Hours
IDX_OPEN_HOUR = 9    # 09:00 WIB
IDX_CLOSE_HOUR = 16  # 16:00 WIB
IDX_TRADING_DAYS = {0, 1, 2, 3, 4}  # Mon-Fri


class SchedulerStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class TaskType(Enum):
    DAILY_FETCH = "daily_fetch"
    INTRADAY_FETCH = "intraday_fetch"
    DATA_CLEAN = "data_clean"
    FEATURE_BUILD = "feature_build"


@dataclass
class SchedulerEvent:
    """Event yang dikirim ke UI callback saat scheduler melakukan aktivitas."""
    timestamp: str
    task: str
    status: str   # "started" | "completed" | "failed"
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class SchedulerConfig:
    """Konfigurasi scheduler."""
    daily_fetch_interval_minutes: int = 60    # Fetch data harian setiap 60 menit
    intraday_interval_minutes: int = 15       # Fetch intraday setiap 15 menit
    auto_clean: bool = True                    # Auto-clean setelah fetch
    auto_features: bool = False                # Auto-build fitur (opsional, berat)
    universe: str = "lq45"                     # Universe ticker
    respect_trading_hours: bool = True         # Hanya aktif saat jam bursa IDX
    max_retries: int = 3                       # Retry limit jika fetch gagal
    retry_delay_seconds: int = 30              # Delay antara retry


class DataScheduler:
    """
    Background Data Scheduler untuk Finance-Pro.

    Menjalankan sinkronisasi data otomatis secara berkala:
    - Daily close price fetch (setiap 60 menit saat jam bursa).
    - Intraday hourly candle fetch (setiap 15 menit saat jam bursa).
    - Auto-cleaning data setelah fetch.

    Thread-safe dan bisa berjalan di background tanpa blocking TUI/GUI.
    """

    def __init__(
        self,
        config: Optional[SchedulerConfig] = None,
        on_event: Optional[Callable[[SchedulerEvent], None]] = None,
    ):
        self.config = config or SchedulerConfig()
        self.on_event = on_event
        self.status = SchedulerStatus.IDLE
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_daily_fetch: Optional[datetime] = None
        self._last_intraday_fetch: Optional[datetime] = None
        self._last_clean: Optional[datetime] = None
        self._history: List[SchedulerEvent] = []
        self._run_count = 0
        self._error_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_background(self) -> None:
        """Mulai scheduler di background thread."""
        with self._lock:
            if self.status == SchedulerStatus.RUNNING:
                logger.warning("Scheduler sudah berjalan, skip start.")
                return

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="DataScheduler",
                daemon=True,
            )
            self._thread.start()
            self.status = SchedulerStatus.RUNNING
            self._emit(TaskType.DAILY_FETCH.value, "started",
                       "Background Data Scheduler started.")
            logger.info("DataScheduler started in background thread.")

    def stop(self) -> None:
        """Hentikan scheduler."""
        with self._lock:
            if self.status != SchedulerStatus.RUNNING:
                return
            self._stop_event.set()
            self.status = SchedulerStatus.STOPPED
            self._emit(TaskType.DAILY_FETCH.value, "completed",
                       "Background Data Scheduler stopped.")
            logger.info("DataScheduler stopped.")

    def is_running(self) -> bool:
        return self.status == SchedulerStatus.RUNNING

    def get_status_summary(self) -> dict:
        """Status ringkasan scheduler untuk ditampilkan di TUI."""
        now = datetime.now(WIB)
        return {
            "status": self.status.value,
            "is_trading_hours": self._is_trading_hours(now),
            "current_time_wib": now.strftime("%Y-%m-%d %H:%M:%S WIB"),
            "last_daily_fetch": self._last_daily_fetch.strftime(
                "%H:%M:%S") if self._last_daily_fetch else "-",
            "last_intraday_fetch": self._last_intraday_fetch.strftime(
                "%H:%M:%S") if self._last_intraday_fetch else "-",
            "last_clean": self._last_clean.strftime(
                "%H:%M:%S") if self._last_clean else "-",
            "total_runs": self._run_count,
            "total_errors": self._error_count,
            "recent_events": self._history[-5:] if self._history else [],
        }

    def get_history(self) -> List[SchedulerEvent]:
        """Ambil histori event scheduler."""
        return list(self._history)

    def run_once(self, force: bool = False) -> dict:
        """
        Jalankan satu siklus fetch + clean secara sinkron.
        Berguna untuk testing atau trigger manual dari CLI.

        Args:
            force: Jika True, abaikan pengecekan jam bursa.

        Returns:
            dict hasil siklus.
        """
        now = datetime.now(WIB)
        results = {"timestamp": now.isoformat(), "tasks": []}

        if not force and self.config.respect_trading_hours:
            if not self._is_trading_hours(now):
                results["skipped"] = True
                results["reason"] = (
                    f"Di luar jam bursa IDX "
                    f"(sekarang: {now.strftime('%A %H:%M WIB')}, "
                    f"Bursa: Sen-Jum 09:00-16:00 WIB)"
                )
                return results

        # Daily fetch
        daily_result = self._do_daily_fetch()
        results["tasks"].append(daily_result)

        # Intraday fetch
        intraday_result = self._do_intraday_fetch()
        results["tasks"].append(intraday_result)

        # Auto-clean
        if self.config.auto_clean:
            clean_result = self._do_data_clean()
            results["tasks"].append(clean_result)

        return results

    # ------------------------------------------------------------------
    # Trading Hours Logic
    # ------------------------------------------------------------------

    @staticmethod
    def _is_trading_hours(now: datetime) -> bool:
        """Cek apakah sekarang jam bursa IDX (Senin-Jumat, 09:00-16:00 WIB)."""
        if now.weekday() not in IDX_TRADING_DAYS:
            return False
        return IDX_OPEN_HOUR <= now.hour < IDX_CLOSE_HOUR

    @staticmethod
    def next_trading_window(now: Optional[datetime] = None) -> datetime:
        """Hitung kapan jam bursa berikutnya dimulai."""
        if now is None:
            now = datetime.now(WIB)

        # Jika masih dalam jam bursa hari ini
        if (now.weekday() in IDX_TRADING_DAYS
                and now.hour < IDX_CLOSE_HOUR):
            if now.hour >= IDX_OPEN_HOUR:
                return now
            return now.replace(hour=IDX_OPEN_HOUR, minute=0, second=0,
                               microsecond=0)

        # Cari hari kerja berikutnya
        candidate = now + timedelta(days=1)
        candidate = candidate.replace(hour=IDX_OPEN_HOUR, minute=0,
                                      second=0, microsecond=0)
        while candidate.weekday() not in IDX_TRADING_DAYS:
            candidate += timedelta(days=1)
        return candidate

    # ------------------------------------------------------------------
    # Background Loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Main loop scheduler di background thread."""
        logger.info("Scheduler loop started.")
        min_interval = min(
            self.config.daily_fetch_interval_minutes,
            self.config.intraday_interval_minutes,
        )
        sleep_seconds = max(min_interval * 60, 60)  # Minimal 60 detik

        while not self._stop_event.is_set():
            try:
                now = datetime.now(WIB)

                if self.config.respect_trading_hours and not self._is_trading_hours(now):
                    # Di luar jam bursa, sleep sampai jam bursa berikutnya
                    next_open = self.next_trading_window(now)
                    wait_seconds = (next_open - now).total_seconds()
                    wait_seconds = min(wait_seconds, 300)  # Max 5 min sleep
                    logger.debug(
                        "Di luar jam bursa. Sleep %.0f detik "
                        "(next open: %s)", wait_seconds,
                        next_open.strftime("%A %H:%M WIB"))
                    self._stop_event.wait(timeout=wait_seconds)
                    continue

                # Daily fetch check
                if self._should_run_daily(now):
                    self._do_daily_fetch()

                # Intraday fetch check
                if self._should_run_intraday(now):
                    self._do_intraday_fetch()

                # Auto-clean after fetch
                if self.config.auto_clean and (
                    self._last_daily_fetch == now or
                    self._last_intraday_fetch == now
                ):
                    self._do_data_clean()

            except Exception as e:
                self._error_count += 1
                logger.error("Scheduler loop error: %s", e, exc_info=True)
                self._emit("scheduler", "failed", f"Loop error: {e}")

            self._stop_event.wait(timeout=sleep_seconds)

        logger.info("Scheduler loop exited.")

    def _should_run_daily(self, now: datetime) -> bool:
        """Cek apakah daily fetch perlu dijalankan."""
        if self._last_daily_fetch is None:
            return True
        elapsed = (now - self._last_daily_fetch).total_seconds() / 60
        return elapsed >= self.config.daily_fetch_interval_minutes

    def _should_run_intraday(self, now: datetime) -> bool:
        """Cek apakah intraday fetch perlu dijalankan."""
        if self._last_intraday_fetch is None:
            return True
        elapsed = (now - self._last_intraday_fetch).total_seconds() / 60
        return elapsed >= self.config.intraday_interval_minutes

    # ------------------------------------------------------------------
    # Task Executors
    # ------------------------------------------------------------------

    def _do_daily_fetch(self) -> dict:
        """Eksekusi daily close price fetch."""
        task = TaskType.DAILY_FETCH.value
        self._emit(task, "started", "Fetching daily close prices...")
        self._run_count += 1

        try:
            from pipeline.universe import UniverseManager
            from pipeline.fetcher import DataFetcher
            from pipeline.storage import StorageManager

            um = UniverseManager(universe_name=self.config.universe)
            tickers = um.get_tickers()
            fetcher = DataFetcher(cache_days=0)  # No cache for scheduler
            storage = StorageManager()

            success = 0
            failed = 0
            for ticker in tickers:
                for attempt in range(self.config.max_retries):
                    try:
                        # Fetch last 30 days only (incremental update)
                        end_date = datetime.now().strftime("%Y-%m-%d")
                        start_date = (
                            datetime.now() - timedelta(days=30)
                        ).strftime("%Y-%m-%d")
                        df = fetcher.fetch_single(
                            ticker, start=start_date, end=end_date)
                        if df is not None and not df.empty:
                            storage.save_prices(ticker, df)
                            success += 1
                        break
                    except Exception as e:
                        if attempt < self.config.max_retries - 1:
                            time.sleep(self.config.retry_delay_seconds)
                        else:
                            failed += 1
                            logger.warning(
                                "Failed to fetch %s after %d retries: %s",
                                ticker, self.config.max_retries, e)

            self._last_daily_fetch = datetime.now(WIB)
            msg = f"Daily fetch done: {success} OK, {failed} failed"
            self._emit(task, "completed", msg,
                       {"success": success, "failed": failed})
            return {"task": task, "status": "completed",
                    "success": success, "failed": failed}

        except Exception as e:
            self._error_count += 1
            msg = f"Daily fetch error: {e}"
            self._emit(task, "failed", msg)
            logger.error(msg, exc_info=True)
            return {"task": task, "status": "failed", "error": str(e)}

    def _do_intraday_fetch(self) -> dict:
        """Eksekusi intraday hourly candle fetch."""
        task = TaskType.INTRADAY_FETCH.value
        self._emit(task, "started", "Fetching intraday hourly candles...")
        self._run_count += 1

        try:
            from pipeline.universe import UniverseManager
            from pipeline.intraday_fetcher import IntradayFetcher
            from pipeline.storage import StorageManager

            um = UniverseManager(universe_name=self.config.universe)
            tickers = um.get_tickers()
            fetcher = IntradayFetcher(batch_size=10, delay_seconds=2)
            storage = StorageManager()

            hourly_df = fetcher.fetch_hourly_batch(tickers, days=7)
            rows_saved = 0
            if hourly_df is not None and not hourly_df.empty:
                # save_intraday expects (ticker, df) per ticker
                for ticker in tickers:
                    if "ticker" in hourly_df.columns:
                        ticker_df = hourly_df[hourly_df["ticker"] == ticker]
                    else:
                        ticker_df = hourly_df.get(ticker, pd.DataFrame())
                    if hasattr(ticker_df, '__len__') and len(ticker_df) > 0:
                        storage.save_intraday(ticker, ticker_df)
                        rows_saved += len(ticker_df)

            self._last_intraday_fetch = datetime.now(WIB)
            msg = f"Intraday fetch done: {rows_saved} rows saved"
            self._emit(task, "completed", msg, {"rows_saved": rows_saved})
            return {"task": task, "status": "completed",
                    "rows_saved": rows_saved}

        except Exception as e:
            self._error_count += 1
            msg = f"Intraday fetch error: {e}"
            self._emit(task, "failed", msg)
            logger.error(msg, exc_info=True)
            return {"task": task, "status": "failed", "error": str(e)}

    def _do_data_clean(self) -> dict:
        """Eksekusi auto-cleaning data."""
        task = TaskType.DATA_CLEAN.value
        self._emit(task, "started", "Running data cleaning pipeline...")
        self._run_count += 1

        try:
            from pipeline.storage import StorageManager
            from pipeline.data_cleaner import DataCleaner

            storage = StorageManager()
            cleaner = DataCleaner()

            raw = storage.load_close_prices()
            cleaned = cleaner.clean(raw)

            self._last_clean = datetime.now(WIB)
            msg = (f"Data cleaned: {raw.shape[1]} tickers, "
                   f"{cleaned.isna().sum().sum()} remaining NaN")
            self._emit(task, "completed", msg,
                       {"tickers": raw.shape[1],
                        "remaining_nan": int(cleaned.isna().sum().sum())})
            return {"task": task, "status": "completed",
                    "tickers": raw.shape[1]}

        except Exception as e:
            self._error_count += 1
            msg = f"Data clean error: {e}"
            self._emit(task, "failed", msg)
            logger.error(msg, exc_info=True)
            return {"task": task, "status": "failed", "error": str(e)}

    # ------------------------------------------------------------------
    # Event Emission
    # ------------------------------------------------------------------

    def _emit(self, task: str, status: str, message: str,
              details: Optional[dict] = None) -> None:
        """Emit event ke callback dan histori internal."""
        event = SchedulerEvent(
            timestamp=datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S"),
            task=task,
            status=status,
            message=message,
            details=details or {},
        )
        self._history.append(event)
        # Keep only last 100 events
        if len(self._history) > 100:
            self._history = self._history[-100:]

        logger.info("[Scheduler] %s | %s | %s", task, status, message)

        if self.on_event:
            try:
                self.on_event(event)
            except Exception as e:
                logger.debug("Event callback error: %s", e)

    def __repr__(self) -> str:
        return (f"DataScheduler(status={self.status.value}, "
                f"runs={self._run_count}, errors={self._error_count})")
