"""
Tests for app/backtest/report.py — HTML + Markdown report generation.
"""
import pandas as pd
import pytest
import tempfile
from pathlib import Path

from app.backtest.report import render_html, render_markdown, render_walkforward_html


@pytest.fixture
def sample_backtest_result():
    """Sample backtest result dict matching Backtester.run() output."""
    dates = pd.date_range("2026-01-01", periods=100, freq="B")
    equity_values = [100_000_000]
    for i in range(99):
        equity_values.append(equity_values[-1] * (1 + (i % 7 - 3) * 0.002))

    return {
        "equity_curve": pd.Series(equity_values, index=dates, name="equity"),
        "trades": [
            {
                "ticker": "BBCA.JK",
                "entry_date": "2026-01-05",
                "exit_date": "2026-01-15",
                "entry_price": 9000.0,
                "exit_price": 9500.0,
                "quantity": 500,
                "pnl": 250000.0,
            },
            {
                "ticker": "BBRI.JK",
                "entry_date": "2026-01-20",
                "exit_date": "2026-02-01",
                "entry_price": 5000.0,
                "exit_price": 4800.0,
                "quantity": 1000,
                "pnl": -200000.0,
            },
        ],
        "metrics": {
            "total_return": 0.05,
            "cagr": 0.12,
            "sharpe_ratio": 1.24,
            "sortino_ratio": 1.85,
            "max_drawdown": -0.08,
            "calmar_ratio": 1.50,
            "j_value": 0.85,
            "annualized_volatility": 0.15,
            "win_rate": 0.55,
            "profit_factor": 1.25,
            "total_trades": 2,
        },
        "strategy": "momentum",
        "strategy_params": {"fast_window": 5, "slow_window": 20},
    }


@pytest.fixture
def sample_walkforward_folds():
    """Sample walk-forward fold results."""
    return [
        {"fold": 1, "accuracy": 0.65, "f1_macro": 0.62, "train_size": 504, "test_size": 126},
        {"fold": 2, "accuracy": 0.67, "f1_macro": 0.64, "train_size": 504, "test_size": 126},
        {"fold": 3, "accuracy": 0.63, "f1_macro": 0.60, "train_size": 504, "test_size": 126},
        {"fold": 4, "accuracy": 0.68, "f1_macro": 0.66, "train_size": 504, "test_size": 126},
        {"fold": 5, "accuracy": 0.64, "f1_macro": 0.61, "train_size": 504, "test_size": 126},
    ]


# ===========================================================================
# HTML Report Tests
# ===========================================================================

class TestRenderHTML:
    def test_creates_file(self, sample_backtest_result):
        """render_html harus membuat file HTML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.html"
            result_path = render_html(sample_backtest_result, out)
            assert result_path.exists()
            assert result_path == out

    def test_html_contains_chart_js(self, sample_backtest_result):
        """HTML harus mengandung Chart.js script."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.html"
            render_html(sample_backtest_result, out)
            content = out.read_text()
            assert "chart.js" in content.lower() or "Chart" in content

    def test_html_contains_metrics(self, sample_backtest_result):
        """HTML harus mengandung metrik performa."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.html"
            render_html(sample_backtest_result, out)
            content = out.read_text()
            assert "Sharpe Ratio" in content
            assert "Max Drawdown" in content
            assert "Total Return" in content

    def test_html_contains_trades(self, sample_backtest_result):
        """HTML harus mengandung tabel trades."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.html"
            render_html(sample_backtest_result, out)
            content = out.read_text()
            assert "BBCA.JK" in content
            assert "BBRI.JK" in content

    def test_html_contains_strategy_info(self, sample_backtest_result):
        """HTML harus mengandung info strategi."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.html"
            render_html(sample_backtest_result, out)
            content = out.read_text()
            assert "momentum" in content

    def test_html_nord_theme_colors(self, sample_backtest_result):
        """HTML harus menggunakan Nord theme colors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.html"
            render_html(sample_backtest_result, out)
            content = out.read_text()
            assert "#2E3440" in content  # Polar Night
            assert "#88C0D0" in content  # Frost

    def test_html_creates_subdirectory(self, sample_backtest_result):
        """render_html harus membuat subdirectory jika belum ada."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "sub" / "dir" / "report.html"
            render_html(sample_backtest_result, out)
            assert out.exists()

    def test_html_empty_result(self):
        """render_html harus handle empty result tanpa crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.html"
            result = {
                "equity_curve": pd.Series(dtype=float),
                "trades": [],
                "metrics": {},
            }
            render_html(result, out)
            assert out.exists()


# ===========================================================================
# Markdown Report Tests
# ===========================================================================

class TestRenderMarkdown:
    def test_returns_string(self, sample_backtest_result):
        """render_markdown harus return string markdown."""
        md = render_markdown(sample_backtest_result)
        assert isinstance(md, str)
        assert len(md) > 0

    def test_contains_metrics_table(self, sample_backtest_result):
        """Markdown harus mengandung tabel metrik."""
        md = render_markdown(sample_backtest_result)
        assert "| Metric | Value |" in md
        assert "Sharpe Ratio" in md
        assert "Max Drawdown" in md

    def test_contains_trades_table(self, sample_backtest_result):
        """Markdown harus mengandung tabel trades."""
        md = render_markdown(sample_backtest_result)
        assert "BBCA.JK" in md
        assert "BBRI.JK" in md

    def test_writes_file(self, sample_backtest_result):
        """render_markdown harus bisa menulis ke file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.md"
            md = render_markdown(sample_backtest_result, output_path=out)
            assert out.exists()
            assert out.read_text() == md

    def test_no_file_without_path(self, sample_backtest_result):
        """render_markdown tanpa output_path hanya return string."""
        md = render_markdown(sample_backtest_result)
        assert isinstance(md, str)

    def test_contains_strategy_info(self, sample_backtest_result):
        """Markdown harus mengandung info strategi."""
        md = render_markdown(sample_backtest_result)
        assert "momentum" in md


# ===========================================================================
# Walk-Forward Report Tests
# ===========================================================================

class TestRenderWalkForwardHTML:
    def test_creates_file(self, sample_walkforward_folds):
        """render_walkforward_html harus membuat file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "wf_report.html"
            result_path = render_walkforward_html(sample_walkforward_folds, out)
            assert result_path.exists()

    def test_contains_fold_data(self, sample_walkforward_folds):
        """HTML harus mengandung data per-fold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "wf_report.html"
            render_walkforward_html(sample_walkforward_folds, out)
            content = out.read_text()
            assert "Fold 1" in content
            assert "Fold 5" in content
            assert "504" in content  # train_size

    def test_contains_nord_theme(self, sample_walkforward_folds):
        """HTML harus menggunakan Nord theme."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "wf_report.html"
            render_walkforward_html(sample_walkforward_folds, out)
            content = out.read_text()
            assert "#2E3440" in content

    def test_empty_folds(self):
        """render_walkforward_html harus handle empty folds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "wf_report.html"
            render_walkforward_html([], out)
            assert out.exists()
