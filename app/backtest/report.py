"""
Backtest Report Generator — HTML (Chart.js) + Markdown export.

Generates professional backtest reports from Backtester.run() results,
including equity curve charts, drawdown analysis, trade logs, and
walk-forward per-fold breakdowns.

Layer 6: app/backtest/ — Risk & Validation.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import logging

logger = logging.getLogger(__name__)

# Template paths
_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _ensure_output_dir(output_path: Path) -> None:
    """Create output directory if needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)


def _format_number(value: float, decimals: int = 2) -> str:
    """Format angka dengan pemisah ribuan."""
    if abs(value) >= 1_000_000:
        return f"Rp {value:,.0f}"
    return f"{value:,.{decimals}f}"


def _format_pct(value: float) -> str:
    """Format persentase."""
    return f"{value * 100:+.2f}%" if abs(value) < 100 else f"{value:+.2f}%"


# ======================================================================
# HTML Report (Chart.js)
# ======================================================================

def render_html(
    result: Dict[str, Any],
    output_path: Path,
    title: str = "Finance-Pro Backtest Report",
) -> Path:
    """
    Render hasil backtest ke file HTML dengan Chart.js equity & drawdown chart.

    Args:
        result: Dict dari Backtester.run() (equity_curve, trades, metrics)
        output_path: File path untuk output HTML
        title: Judul laporan

    Returns:
        Path ke file HTML yang dihasilkan
    """
    _ensure_output_dir(output_path)

    equity_curve = result.get("equity_curve")
    metrics = result.get("metrics", {})
    trades = result.get("trades", [])
    strategy = result.get("strategy", "unknown")
    strategy_params = result.get("strategy_params", {})

    # Prepare equity data for Chart.js
    equity_labels = []
    equity_values = []
    drawdown_values = []

    if equity_curve is not None and len(equity_curve) > 0:
        peak = equity_curve.iloc[0]
        for date, value in equity_curve.items():
            equity_labels.append(str(date)[:10])
            equity_values.append(round(float(value), 2))
            if value > peak:
                peak = value
            dd = ((value - peak) / peak) * 100 if peak > 0 else 0
            drawdown_values.append(round(float(dd), 4))

    # Build metrics table rows
    metric_rows = ""
    key_metrics = [
        ("Total Return", metrics.get("total_return", 0), True),
        ("CAGR", metrics.get("cagr", 0), True),
        ("Sharpe Ratio", metrics.get("sharpe_ratio", 0), False),
        ("Sortino Ratio", metrics.get("sortino_ratio", 0), False),
        ("Max Drawdown", metrics.get("max_drawdown", 0), True),
        ("Calmar Ratio", metrics.get("calmar_ratio", 0), False),
        ("J-Value Score", metrics.get("j_value", 0), False),
        ("Annualized Volatility", metrics.get("annualized_volatility", 0), True),
        ("Win Rate", metrics.get("win_rate", 0), True),
        ("Profit Factor", metrics.get("profit_factor", 0), False),
        ("Total Trades", metrics.get("total_trades", 0), False),
    ]
    for name, value, is_pct in key_metrics:
        if is_pct and isinstance(value, (int, float)):
            display = _format_pct(value) if abs(value) < 10 else f"{value:.2f}%"
        else:
            display = f"{value:.4f}" if isinstance(value, float) else str(value)
        metric_rows += f"<tr><td>{name}</td><td>{display}</td></tr>\n"

    # Build trades table (last 50)
    trade_rows = ""
    for t in trades[-50:]:
        pnl = t.get("pnl", 0)
        pnl_class = "positive" if pnl >= 0 else "negative"
        trade_rows += (
            f"<tr>"
            f"<td>{t.get('ticker', '-')}</td>"
            f"<td>{t.get('entry_date', '-')}</td>"
            f"<td>{t.get('exit_date', '-')}</td>"
            f"<td>Rp {t.get('entry_price', 0):,.0f}</td>"
            f"<td>Rp {t.get('exit_price', 0):,.0f}</td>"
            f"<td>{t.get('quantity', 0)}</td>"
            f"<td class='{pnl_class}'>Rp {pnl:,.0f}</td>"
            f"</tr>\n"
        )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S WIB")

    html = _HTML_TEMPLATE.format(
        title=title,
        strategy=strategy,
        strategy_params=json.dumps(strategy_params, indent=2),
        generated_at=generated_at,
        equity_labels=json.dumps(equity_labels),
        equity_values=json.dumps(equity_values),
        drawdown_values=json.dumps(drawdown_values),
        metric_rows=metric_rows,
        trade_rows=trade_rows,
        n_trades=len(trades),
    )

    output_path.write_text(html, encoding="utf-8")
    logger.info("HTML report written to %s", output_path)
    return output_path


# ======================================================================
# Walk-Forward Report (HTML)
# ======================================================================

def render_walkforward_html(
    folds: List[Dict],
    output_path: Path,
    title: str = "Walk-Forward Validation Report",
) -> Path:
    """
    Render walk-forward validation per-fold ke HTML.

    Args:
        folds: List of dict per-fold dari WalkForwardValidator.validate()
        output_path: File path output

    Returns:
        Path ke file HTML
    """
    _ensure_output_dir(output_path)

    fold_rows = ""
    for f in folds:
        fold_id = f.get("fold", "?")
        accuracy = f.get("accuracy", 0)
        f1 = f.get("f1_macro", 0)
        train_size = f.get("train_size", 0)
        test_size = f.get("test_size", 0)
        error = f.get("error", "")

        status = "✓ PASS" if not error else f"✗ {error}"
        fold_rows += (
            f"<tr>"
            f"<td>Fold {fold_id}</td>"
            f"<td>{train_size:,}</td>"
            f"<td>{test_size:,}</td>"
            f"<td>{accuracy:.4f}</td>"
            f"<td>{f1:.4f}</td>"
            f"<td>{status}</td>"
            f"</tr>\n"
        )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S WIB")

    html = _WF_HTML_TEMPLATE.format(
        title=title,
        generated_at=generated_at,
        n_folds=len(folds),
        fold_rows=fold_rows,
    )

    output_path.write_text(html, encoding="utf-8")
    logger.info("Walk-forward report written to %s", output_path)
    return output_path


# ======================================================================
# Markdown Report
# ======================================================================

def render_markdown(
    result: Dict[str, Any],
    output_path: Optional[Path] = None,
    title: str = "Finance-Pro Backtest Report",
) -> str:
    """
    Render hasil backtest ke format Markdown.

    Args:
        result: Dict dari Backtester.run()
        output_path: Opsional file path; jika None, hanya return string
        title: Judul laporan

    Returns:
        String markdown
    """
    metrics = result.get("metrics", {})
    trades = result.get("trades", [])
    strategy = result.get("strategy", "unknown")
    strategy_params = result.get("strategy_params", {})
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S WIB")

    lines = [
        f"# {title}",
        "",
        f"**Generated:** {generated_at}  ",
        f"**Strategy:** {strategy}  ",
        f"**Parameters:** `{json.dumps(strategy_params)}`  ",
        "",
        "---",
        "",
        "## Performance Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
    ]

    key_metrics = [
        ("Total Return", metrics.get("total_return", 0), True),
        ("CAGR", metrics.get("cagr", 0), True),
        ("Sharpe Ratio", metrics.get("sharpe_ratio", 0), False),
        ("Sortino Ratio", metrics.get("sortino_ratio", 0), False),
        ("Max Drawdown", metrics.get("max_drawdown", 0), True),
        ("Calmar Ratio", metrics.get("calmar_ratio", 0), False),
        ("J-Value Score", metrics.get("j_value", 0), False),
        ("Annualized Volatility", metrics.get("annualized_volatility", 0), True),
        ("Win Rate", metrics.get("win_rate", 0), True),
        ("Profit Factor", metrics.get("profit_factor", 0), False),
        ("Total Trades", metrics.get("total_trades", 0), False),
    ]

    for name, value, is_pct in key_metrics:
        if is_pct and isinstance(value, (int, float)):
            display = _format_pct(value) if abs(value) < 10 else f"{value:.2f}%"
        else:
            display = f"{value:.4f}" if isinstance(value, float) else str(value)
        lines.append(f"| {name} | {display} |")

    lines.extend([
        "",
        "---",
        "",
        f"## Trade Log (Last {min(len(trades), 30)} of {len(trades)} trades)",
        "",
        "| Ticker | Entry Date | Exit Date | Entry Price | Exit Price | Qty | P/L |",
        "|--------|------------|-----------|-------------|------------|-----|-----|",
    ])

    for t in trades[-30:]:
        pnl = t.get("pnl", 0)
        pnl_str = f"Rp {pnl:+,.0f}"
        lines.append(
            f"| {t.get('ticker', '-')} "
            f"| {t.get('entry_date', '-')} "
            f"| {t.get('exit_date', '-')} "
            f"| Rp {t.get('entry_price', 0):,.0f} "
            f"| Rp {t.get('exit_price', 0):,.0f} "
            f"| {t.get('quantity', 0)} "
            f"| {pnl_str} |"
        )

    lines.extend(["", "---", f"", f"*Report generated by Finance-Pro Quant Engine*"])

    md_content = "\n".join(lines)

    if output_path:
        _ensure_output_dir(output_path)
        output_path.write_text(md_content, encoding="utf-8")
        logger.info("Markdown report written to %s", output_path)

    return md_content


# ======================================================================
# HTML Templates (inline — no external dependency)
# ======================================================================

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #2E3440; --bg2: #3B4252; --fg: #ECEFF4;
    --frost: #88C0D0; --blue: #5E81AC; --green: #A3BE8C;
    --red: #BF616A; --yellow: #EBCB8B; --orange: #D08770;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--fg); padding: 24px; }}
  h1 {{ color: var(--frost); margin-bottom: 4px; font-size: 1.6em; }}
  h2 {{ color: var(--frost); margin: 24px 0 12px; font-size: 1.2em; border-bottom: 1px solid var(--bg2); padding-bottom: 6px; }}
  .meta {{ color: #81A1C1; font-size: 0.9em; margin-bottom: 16px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
  .card {{ background: var(--bg2); border-radius: 8px; padding: 16px; }}
  .chart-container {{ position: relative; height: 300px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
  th {{ background: var(--bg2); color: var(--frost); text-align: left; padding: 8px 12px; }}
  td {{ padding: 6px 12px; border-bottom: 1px solid #434C5E; }}
  tr:hover {{ background: rgba(136, 192, 208, 0.08); }}
  .positive {{ color: var(--green); font-weight: 600; }}
  .negative {{ color: var(--red); font-weight: 600; }}
  .footer {{ text-align: center; color: #4C566A; margin-top: 32px; font-size: 0.8em; }}
</style>
</head>
<body>
<h1>📊 {title}</h1>
<div class="meta">
  Strategy: <strong>{strategy}</strong> &nbsp;│&nbsp;
  Generated: {generated_at} &nbsp;│&nbsp;
  Trades: {n_trades}
</div>

<div class="grid">
  <div class="card">
    <h2>Equity Curve (NAV)</h2>
    <div class="chart-container"><canvas id="equityChart"></canvas></div>
  </div>
  <div class="card">
    <h2>Drawdown (%)</h2>
    <div class="chart-container"><canvas id="ddChart"></canvas></div>
  </div>
</div>

<div class="card">
  <h2>Performance Metrics</h2>
  <table>
    <thead><tr><th>Metric</th><th>Value</th></tr></thead>
    <tbody>{metric_rows}</tbody>
  </table>
</div>

<div class="card" style="margin-top:20px">
  <h2>Trade Log (Last 50)</h2>
  <table>
    <thead>
      <tr><th>Ticker</th><th>Entry</th><th>Exit</th><th>Entry Price</th><th>Exit Price</th><th>Qty</th><th>P/L</th></tr>
    </thead>
    <tbody>{trade_rows}</tbody>
  </table>
</div>

<div class="footer">
  Finance-Pro Quant Engine — Backtest Report<br>
  Strategy Parameters: <code>{strategy_params}</code>
</div>

<script>
const labels = {equity_labels};
const equityData = {equity_values};
const ddData = {drawdown_values};

new Chart(document.getElementById('equityChart'), {{
  type: 'line',
  data: {{
    labels: labels,
    datasets: [{{ label: 'NAV (Rp)', data: equityData, borderColor: '#88C0D0', backgroundColor: 'rgba(136,192,208,0.1)', fill: true, tension: 0.1, pointRadius: 0 }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    scales: {{ x: {{ display: true, ticks: {{ maxTicksLimit: 10, color: '#81A1C1' }}, grid: {{ color: '#3B4252' }} }}, y: {{ ticks: {{ color: '#81A1C1' }}, grid: {{ color: '#3B4252' }} }} }},
    plugins: {{ legend: {{ labels: {{ color: '#ECEFF4' }} }} }}
  }}
}});

new Chart(document.getElementById('ddChart'), {{
  type: 'line',
  data: {{
    labels: labels,
    datasets: [{{ label: 'Drawdown (%)', data: ddData, borderColor: '#BF616A', backgroundColor: 'rgba(191,97,106,0.15)', fill: true, tension: 0.1, pointRadius: 0 }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    scales: {{ x: {{ display: true, ticks: {{ maxTicksLimit: 10, color: '#81A1C1' }}, grid: {{ color: '#3B4252' }} }}, y: {{ ticks: {{ color: '#81A1C1' }}, grid: {{ color: '#3B4252' }} }} }},
    plugins: {{ legend: {{ labels: {{ color: '#ECEFF4' }} }} }}
  }}
}});
</script>
</body>
</html>"""


_WF_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{ --bg: #2E3440; --bg2: #3B4252; --fg: #ECEFF4; --frost: #88C0D0; --green: #A3BE8C; --red: #BF616A; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--fg); padding: 24px; }}
  h1 {{ color: var(--frost); margin-bottom: 4px; font-size: 1.6em; }}
  h2 {{ color: var(--frost); margin: 24px 0 12px; font-size: 1.2em; border-bottom: 1px solid var(--bg2); padding-bottom: 6px; }}
  .meta {{ color: #81A1C1; font-size: 0.9em; margin-bottom: 16px; }}
  .card {{ background: var(--bg2); border-radius: 8px; padding: 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
  th {{ background: var(--bg2); color: var(--frost); text-align: left; padding: 8px 12px; }}
  td {{ padding: 6px 12px; border-bottom: 1px solid #434C5E; }}
  tr:hover {{ background: rgba(136, 192, 208, 0.08); }}
  .footer {{ text-align: center; color: #4C566A; margin-top: 32px; font-size: 0.8em; }}
</style>
</head>
<body>
<h1>📈 {title}</h1>
<div class="meta">
  Walk-Forward Folds: <strong>{n_folds}</strong> &nbsp;│&nbsp;
  Generated: {generated_at}
</div>

<div class="card">
  <h2>Per-Fold Results</h2>
  <table>
    <thead>
      <tr><th>Fold</th><th>Train Size</th><th>Test Size</th><th>Accuracy</th><th>F1 Macro</th><th>Status</th></tr>
    </thead>
    <tbody>{fold_rows}</tbody>
  </table>
</div>

<div class="footer">Finance-Pro Quant Engine — Walk-Forward Validation Report</div>
</body>
</html>"""
