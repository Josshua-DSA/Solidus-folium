"""
Valuation Engine — DCF, pricing model, dan metode valuasi lainnya.
Refactored dari backend/financial_engine/.

Stateless, zero external layer dependency.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Union
import logging

logger = logging.getLogger(__name__)


class DCFValuation:
    """
    Discounted Cash Flow (DCF) valuation engine.

    Semua perhitungan fiat menggunakan Decimal untuk presisi.
    """

    @staticmethod
    def present_value(
        future_value: Union[float, Decimal],
        rate: float,
        periods: int,
    ) -> Decimal:
        """
        Hitung Present Value dari single future cashflow.

        PV = FV / (1 + r)^n

        Args:
            future_value: Nilai masa depan
            rate: Discount rate per periode (e.g., 0.10 = 10%)
            periods: Jumlah periode

        Returns:
            Present value (Decimal)
        """
        fv = Decimal(str(future_value))
        r = Decimal(str(rate))
        n = periods
        pv = fv / (1 + r) ** n
        return pv.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def net_present_value(
        cashflows: List[Union[float, Decimal]],
        rate: float,
    ) -> Decimal:
        """
        Hitung Net Present Value dari serangkaian cashflow.

        NPV = Σ CF_t / (1 + r)^t

        Args:
            cashflows: List cashflow per periode (index 0 = t=0)
            rate: Discount rate per periode

        Returns:
            NPV (Decimal)
        """
        r = Decimal(str(rate))
        npv = Decimal("0")
        for t, cf in enumerate(cashflows):
            cf_dec = Decimal(str(cf))
            npv += cf_dec / (1 + r) ** t
        return npv.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def dcf_intrinsic_value(
        free_cashflows: List[Union[float, Decimal]],
        terminal_growth_rate: float,
        discount_rate: float,
        shares_outstanding: int,
    ) -> Decimal:
        """
        Hitung intrinsic value per share menggunakan DCF 2-stage model.

        Args:
            free_cashflows: Projected FCF untuk N tahun ke depan
            terminal_growth_rate: Growth rate terminal (perpetuity)
            discount_rate: WACC atau required rate of return
            shares_outstanding: Jumlah saham beredar

        Returns:
            Intrinsic value per share (Decimal)
        """
        r = Decimal(str(discount_rate))
        g = Decimal(str(terminal_growth_rate))

        # Stage 1: PV of projected cashflows
        pv_stage1 = Decimal("0")
        for t, cf in enumerate(free_cashflows, start=1):
            cf_dec = Decimal(str(cf))
            pv_stage1 += cf_dec / (1 + r) ** t

        # Stage 2: Terminal value (Gordon Growth Model)
        last_cf = Decimal(str(free_cashflows[-1]))
        terminal_cf = last_cf * (1 + g)
        terminal_value = terminal_cf / (r - g)
        n = len(free_cashflows)
        pv_terminal = terminal_value / (1 + r) ** n

        # Total enterprise value
        enterprise_value = pv_stage1 + pv_terminal

        # Per share
        per_share = enterprise_value / Decimal(str(shares_outstanding))
        return per_share.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def __repr__(self) -> str:
        return "DCFValuation()"
