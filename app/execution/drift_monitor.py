"""
Drift Monitor — Deteksi anomali risiko secara real-time.

Melacak equity curve setelah setiap trade dan men-emit DriftEvent
ketika drawdown atau daily loss melebihi batas yang ditetapkan.

Layer 5: app/execution/ — Risk Drift Detection.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import pandas as pd
import logging

logger = logging.getLogger(__name__)


@dataclass
class DriftEvent:
    """Satu event anomali risiko yang terdeteksi."""
    timestamp: datetime
    event_type: str        # "DRAWDOWN_BREACH" | "DAILY_LOSS_BREACH" | "POSITION_CONCENTRATION"
    severity: str          # "WARNING" | "CRITICAL"
    equity: float          # NAV saat event
    metric_value: float    # drawdown % atau daily loss %
    threshold: float       # batas yang dilanggar
    message: str


class DriftMonitor:
    """
    Monitor risiko real-time yang melacak equity curve per-trade.

    Setelah setiap update (trade baru), memeriksa:
      1. Max drawdown vs batas stop
      2. Daily loss vs batas harian
      3. Konsentrasi posisi (opsional)

    Semua event dicatat di self.events dan dapat di-query oleh UI.

    Args:
        max_drawdown_stop: Trigger drawdown stop (default -15%)
        daily_loss_limit: Batas kerugian harian (default -3%)
        max_position_pct: Batas konsentrasi posisi (default 10%)
    """

    def __init__(
        self,
        max_drawdown_stop: float = -0.15,
        daily_loss_limit: float = -0.03,
        max_position_pct: float = 0.10,
    ):
        self.max_drawdown_stop = max_drawdown_stop
        self.daily_loss_limit = daily_loss_limit
        self.max_position_pct = max_position_pct

        # State
        self._equity_points: List[Tuple[datetime, float]] = []
        self.events: List[DriftEvent] = []
        self._peak_equity: float = 0.0
        self._day_open_equity: Dict[str, float] = {}  # date_str -> equity at day open

    # ------------------------------------------------------------------
    # Core update — dipanggil setelah setiap trade
    # ------------------------------------------------------------------

    def update(
        self,
        equity: float,
        timestamp: Optional[pd.Timestamp] = None,
        positions_weights: Optional[Dict[str, float]] = None,
    ) -> List[DriftEvent]:
        """
        Update equity curve dan jalankan semua risk checks.

        Args:
            equity: Total portfolio value (NAV) saat ini
            timestamp: Waktu snapshot (default: now)
            positions_weights: Dict ticker -> weight (0-1) untuk cek konsentrasi

        Returns:
            List DriftEvent baru yang terdeteksi pada update ini
        """
        ts = timestamp or pd.Timestamp.now()
        ts_dt = ts.to_pydatetime() if isinstance(ts, pd.Timestamp) else ts
        self._equity_points.append((ts_dt, equity))

        new_events: List[DriftEvent] = []

        # 1. Drawdown check
        dd_event = self._check_drawdown(equity, ts_dt)
        if dd_event:
            new_events.append(dd_event)

        # 2. Daily loss check
        dl_event = self._check_daily_loss(equity, ts_dt)
        if dl_event:
            new_events.append(dl_event)

        # 3. Position concentration check
        if positions_weights:
            conc_events = self._check_concentration(positions_weights, equity, ts_dt)
            new_events.extend(conc_events)

        self.events.extend(new_events)
        return new_events

    # ------------------------------------------------------------------
    # Risk checks
    # ------------------------------------------------------------------

    def _check_drawdown(self, equity: float, ts: datetime) -> Optional[DriftEvent]:
        """Cek apakah drawdown melebihi batas."""
        if equity > self._peak_equity:
            self._peak_equity = equity

        if self._peak_equity <= 0:
            return None

        current_dd = (equity - self._peak_equity) / self._peak_equity

        if current_dd < self.max_drawdown_stop:
            severity = "CRITICAL" if current_dd < self.max_drawdown_stop * 1.5 else "WARNING"
            msg = (
                f"Drawdown {current_dd:.2%} melebihi batas {self.max_drawdown_stop:.2%}. "
                f"NAV: {equity:,.0f}, Peak: {self._peak_equity:,.0f}"
            )
            logger.warning(msg)
            return DriftEvent(
                timestamp=ts,
                event_type="DRAWDOWN_BREACH",
                severity=severity,
                equity=equity,
                metric_value=current_dd,
                threshold=self.max_drawdown_stop,
                message=msg,
            )
        return None

    def _check_daily_loss(self, equity: float, ts: datetime) -> Optional[DriftEvent]:
        """Cek apakah kerugian harian melebihi batas."""
        date_key = ts.strftime("%Y-%m-%d")

        if date_key not in self._day_open_equity:
            self._day_open_equity[date_key] = equity
            return None

        day_open = self._day_open_equity[date_key]
        if day_open <= 0:
            return None

        daily_return = (equity - day_open) / day_open

        if daily_return < self.daily_loss_limit:
            severity = "CRITICAL" if daily_return < self.daily_loss_limit * 2 else "WARNING"
            msg = (
                f"Daily loss {daily_return:.2%} melebihi batas {self.daily_loss_limit:.2%}. "
                f"Day open: {day_open:,.0f}, Current: {equity:,.0f}"
            )
            logger.warning(msg)
            return DriftEvent(
                timestamp=ts,
                event_type="DAILY_LOSS_BREACH",
                severity=severity,
                equity=equity,
                metric_value=daily_return,
                threshold=self.daily_loss_limit,
                message=msg,
            )
        return None

    def _check_concentration(
        self,
        weights: Dict[str, float],
        equity: float,
        ts: datetime,
    ) -> List[DriftEvent]:
        """Cek apakah ada posisi yang melebihi batas konsentrasi."""
        events = []
        for ticker, weight in weights.items():
            if weight > self.max_position_pct:
                msg = (
                    f"Posisi {ticker} terkonsentrasi {weight:.2%} "
                    f"(batas {self.max_position_pct:.2%})"
                )
                logger.warning(msg)
                events.append(DriftEvent(
                    timestamp=ts,
                    event_type="POSITION_CONCENTRATION",
                    severity="WARNING",
                    equity=equity,
                    metric_value=weight,
                    threshold=self.max_position_pct,
                    message=msg,
                ))
        return events

    # ------------------------------------------------------------------
    # Query methods — untuk UI / reporting
    # ------------------------------------------------------------------

    def recent_events(self, n: int = 10) -> List[DriftEvent]:
        """Return N event terbaru."""
        return self.events[-n:]

    def events_by_type(self, event_type: str) -> List[DriftEvent]:
        """Filter events berdasarkan tipe."""
        return [e for e in self.events if e.event_type == event_type]

    def critical_events(self) -> List[DriftEvent]:
        """Return semua event CRITICAL."""
        return [e for e in self.events if e.severity == "CRITICAL"]

    @property
    def current_drawdown(self) -> float:
        """Return current drawdown percentage."""
        if not self._equity_points or self._peak_equity <= 0:
            return 0.0
        latest_equity = self._equity_points[-1][1]
        return (latest_equity - self._peak_equity) / self._peak_equity

    @property
    def equity_series(self) -> pd.Series:
        """Return equity curve sebagai pd.Series (index=datetime)."""
        if not self._equity_points:
            return pd.Series(dtype=float)
        dates, values = zip(*self._equity_points)
        return pd.Series(values, index=pd.DatetimeIndex(dates), name="equity")

    @property
    def total_events(self) -> int:
        """Total jumlah drift events."""
        return len(self.events)

    def get_summary(self) -> Dict:
        """Return ringkasan status drift monitor."""
        return {
            "total_events": self.total_events,
            "critical_count": len(self.critical_events()),
            "drawdown_breaches": len(self.events_by_type("DRAWDOWN_BREACH")),
            "daily_loss_breaches": len(self.events_by_type("DAILY_LOSS_BREACH")),
            "concentration_warnings": len(self.events_by_type("POSITION_CONCENTRATION")),
            "current_drawdown": self.current_drawdown,
            "peak_equity": self._peak_equity,
            "latest_equity": self._equity_points[-1][1] if self._equity_points else 0.0,
            "n_equity_points": len(self._equity_points),
        }

    def __repr__(self) -> str:
        return (
            f"DriftMonitor(events={self.total_events}, "
            f"dd={self.current_drawdown:.2%}, "
            f"peak={self._peak_equity:,.0f})"
        )
