"""
Health Report — Rich-formatted status report (Nord theme).
"""
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class HealthReport:
    """
    Generates and displays health check reports.
    Uses Nord theme colors for status indicators.
    """

    # Nord theme colors
    COLOR_OK = "#A3BE8C"      # Aurora Green
    COLOR_FAIL = "#BF616A"    # Aurora Red
    COLOR_SKIP = "#EBCB8B"    # Aurora Yellow
    COLOR_HEADER = "#88C0D0"  # Frost

    def format_report(self, results: Dict[str, Dict[str, str]]) -> str:
        """
        Format health check results as a report string.

        Args:
            results: Dict dari HealthChecker.check_all()

        Returns:
            Formatted report string
        """
        lines = ["═" * 50, "  HEALTH CHECK REPORT", "═" * 50, ""]

        for category, apis in results.items():
            lines.append(f"  [{category.upper()}]")
            for api_name, status in apis.items():
                icon = {"OK": "✓", "FAIL": "✗", "SKIP": "○"}.get(status, "?")
                lines.append(f"    {icon} {api_name}: {status}")
            lines.append("")

        # Summary
        total = sum(len(v) for v in results.values())
        ok = sum(1 for v in results.values() for s in v.values() if s == "OK")
        fail = sum(1 for v in results.values() for s in v.values() if s == "FAIL")
        skip = sum(1 for v in results.values() for s in v.values() if s == "SKIP")

        lines.append("─" * 50)
        lines.append(f"  Total: {total} | OK: {ok} | FAIL: {fail} | SKIP: {skip}")
        lines.append("═" * 50)

        return "\n".join(lines)

    def __repr__(self) -> str:
        return "HealthReport()"
