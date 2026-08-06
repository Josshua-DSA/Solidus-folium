# 📈 Quant Trading IDX (v7)

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![IDX Compliant](https://img.shields.io/badge/Exchange-IDX-orange.svg)](https://www.idx.co.id/)

An enterprise-grade, multi-layered Quantitative Trading and Algorithmic Execution framework tailored for the **Indonesian Stock Exchange (IDX)**. This system integrates robust financial mathematics, machine learning ensembles, walk-forward validation, and pre-trade risk controls with strict exchange-compliant order simulation.

---

## 🛠 Key Architecture & Features

This codebase is split into modular layers designed to mirror professional institutional setups:

### 1. Data Layer (`data_layer/`)
* **Universe Manager:** Dynamically handles trading universes (e.g., `LQ45`, `Kompas100`, or custom baskets).
* **Data Fetcher & Storage:** Automated daily and intraday downloading from `yfinance` with configurable caching and persistent SQLite integration.
* **Data Cleaner:** Cleans corporate actions, filters extreme anomalies, and prepares prices for mathematical operations.

### 2. Feature Engineering & Labeling (`shared/features/`)
* **Fractional Differentiation:** Preserves long-term memory in price series while achieving stationarity.
* **Triple Barrier Method:** Advanced labeling technique incorporating dynamic vertical barriers (holding time) and horizontal barriers (take-profit/stop-loss).
* **Lasso Feature Selection:** Filters noise and selects top predictive features for machine learning models.

### 3. Alpha & Machine Learning Models (`model/`)
* **Gradient Boosted Decision Trees:** Integrated `XGBoost` and `LightGBM` classifiers tuned for multi-class classification (Profit/Loss/Neutral).
* **Supervised Autoencoders:** Dimensions reduction mapping features into lower-dimensional space while preserving labels.
* **Walk-Forward Validation:** Robust backtesting validation (`Expanding` & `Rolling` modes) mimicking real-world walk-forward training windows (`train_window: 504`, `test_window: 126`).
* **Ensemble Predictor:** Combines tree models with sequence neural network representations.

### 4. Portfolio Optimization & Risk Management (`app/`)
* **Portfolio Optimizer:** Optimizes asset weights under specific transaction costs, turnover penalties, and drawdown limits.
* **Pre-Trade Risk Inspection:** Enforces strict limits:
  * Maximum weight per ticker (`max_position_pct: 10%`).
  * Maximum sector exposure (`max_sector_pct: 30%`).
  * Real-time portfolio drawdown stop-loss and daily loss limits.
  * 95% Historical Value-at-Risk (VaR) threshold inspection.

### 5. Algorithmic Execution Engine (`app/execution/`)
* **IDX Constraints Enforcement:** Enforces minimum lot size rules (1 lot = 100 shares) and standard commission/slippage.
* **VWAP Simulation:** Simulates execution prices based on average volume profiles or custom slippage models.

---

## 📂 Project Directory Structure

``` text
Finance-Pro/
│
├── cli.py                            # Single CLI entry point (Typer + Rich)
├── pyproject.toml
├── requirements.txt
├── README.md
│
├── config/
│   └── config.yaml
│
├── context/                          # Documentation & AI Agent Context
│   ├── [[ARCHITECTURE]]
│   ├── [[DESIGN]]
│   ├── [[PRD]]
│   ├── [[RULES]]
│   ├── [[SCHEMA]]
│   ├── [[STRATEGY]]
│   ├── [[IMPLEMENTATION]]
│   └── [[checkpoint]]
│
├── data/                             # Storage murni / DB — BUKAN Python package
│   ├── ihsg_trading.db
│   ├── raw/
│   └── processed/
│
├── pipeline/                         # Layer 1: Data Ingestion
│   ├── __init__.py
│   ├── universe.py
│   ├── fetcher.py
│   ├── crypto_fetcher.py
│   ├── storage.py
│   ├── data_cleaner.py
│   └── blacklist.py
│
├── shared/                           # Shared Utilities & Financial Math (Stateless/OOP)
│   ├── features/                     # Feature Engineering
│   │   ├── feature_builder.py
│   │   ├── feature_selection.py
│   │   ├── fundamental_features.py
│   │   ├── fractional_diff.py
│   │   └── triple_barrier.py
│   ├── financial_math/               # Pure Math & Valuation Engine
│   │   ├── valuation.py              # DCF, pricing model
│   │   └── cashflow_metrics.py       # Cashflow, ratio & return math
│   └── utils/                        # Logging, helper, UI utilities
│       ├── config_loader.py
│       ├── logger.py
│       ├── helper.py
│       └── ui_renderer.py
│
├── model/                            # Layer 3: Alpha Models & ML R&D
│   ├── __init__.py
│   ├── trainer.py
│   ├── evaluator.py
│   ├── ensemble.py
│   ├── autoencoder.py
│   ├── walk_forward.py
│   ├── xgboost_trainer.py
│   └── lightgbm_trainer.py
│
├── app/                              # Layer 4–6: Quant Pipeline & Trading Engine
│   ├── __init__.py
│   ├── backtest/
│   │   ├── backtester.py
│   │   ├── walk_forward.py           # DI — tidak import model/ langsung
│   │   ├── transaction_cost.py
│   │   └── benchmark_runner.py
│   ├── execution/
│   │   ├── position_manager.py
│   │   └── paper_executor.py
│   ├── optimization/
│   │   ├── portfolio_optimizer.py
│   │   └── risk_model.py
│   ├── risk/
│   │   └── risk_manager.py
│   └── strategies/
│       ├── base_strategy.py
│       ├── strategy_registry.py
│       └── signal_combiner.py
│
├── frontend/                         # User Interface Layer (CLI TUI & Web GUI)
│   ├── cli/
│   │   ├── app.py
│   │   ├── dashboard.py
│   │   ├── scanner.py
│   │   ├── tui_runner.py
│   │   └── ui/
│   ├── gui/
│   └── README.md
│
├── health/                           # External API Connectivity & Diagnostics
│   ├── health_checker.py
│   ├── health_report.py
│   └── apis/
│       ├── broker/
│       ├── llm/
│       ├── data_api/
│       └── trading_view/
│
├── Research_and_Journal/             # Research & Literature per Layer
│   ├── layer-2/
│   ├── layer-3/
│   ├── layer-4/
│   ├── layer-5/
│   └── layer-6/
│
└── tests/                            # Unit Tests (root level)
    ├── test_data_cleaner.py
    ├── test_storage.py
    ├── test_layer2_features.py
    └── test_layer3_models.py

```
---

## ⚡ Quick Start

### 1. Prerequisites & Virtual Environment

Ensure you have **Python 3.11+** installed. Clone the repository and initialize the environment:

```bash
# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# Install dependencies
pip install -r requirements.txt
```

### 2. Running the System CLI

The system provides a rich, color-coded Command Line Interface (CLI) powered by `Rich` and `Typer`:

#### A. Cek Status Database & Pipeline
Verify your local database and setup configuration:
```bash
python cli.py status
```

#### B. Fetch Stock Market Data
Download stock data for a given universe (e.g. `lq45` or `kompas100`) between specified date ranges:
```bash
python cli.py fetch --universe lq45 --start 2015-01-01 --end 2025-12-31
```

#### C. Run the DataCleaner Pipeline
Process raw data, adjust for splits/dividends, and clean pricing issues:
```bash
python cli.py clean
```

#### D. Extract & Construct Technical Features
Extract technical indicators, build triple barrier bounds, and compute fractional returns:
```bash
python cli.py features
```

#### E. Run Backtest Simulation (Baseline Mode)
Simulate trading strategies:
```bash
python cli.py backtest --capital 100000000
```

---

## ⚙ Configuration Parameters (`config/config.yaml`)

You can fully control how the pipeline behaves, including constraints and hyper-parameters, by editing `config/config.yaml`:

```yaml
# Data Configuration
data:
  db_path: "data/ihsg_trading.db"
  start_date: "2015-01-01"

# Risk Controls (Checked Pre-Trade)
risk:
  max_position_pct: 0.10     # Max 10% weight per ticker
  max_sector_pct: 0.30       # Max 30% weight per sector
  daily_loss_limit: -0.03    # Stop-loss at 3% daily portfolio loss
  max_drawdown_stop: -0.15   # System halt at 15% Max Drawdown

# Exchange-Specific Constraints (IDX)
execution:
  lot_size: 100              # Must be multiples of 100 shares
  vwap_simulation: true
```

---

## 🧪 Running Tests

Ensure system consistency and mathematical logic are valid by running the test suite:

```bash
./venv/bin/pytest
```

---

## 🛡 Disclaimer
This software is built for informational, research, and simulation purposes only. Algorithmic trading carries high risk, particularly in emerging markets like IDX. Past performance is not indicative of future results.
