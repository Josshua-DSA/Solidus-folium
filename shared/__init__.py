"""
Shared Package — Kode bersama yang dipakai oleh model/ DAN app/.

Sub-packages:
  - features/        : Feature Engineering (teknikal, TBL, fractional diff, fundamental)
  - financial_math/  : Pure Math & Valuation Engine (DCF, cashflow metrics)
  - utils/           : Logging, config loader, helper, UI renderer

ATURAN KETAT:
  - Zero External Layer Dependency — TIDAK boleh import dari pipeline/, model/, app/, atau frontend/
  - No Side-Effects — semua fungsi bersifat pure calculation / stateless
  - Universal Importability — aman di-import dari folder manapun
"""
