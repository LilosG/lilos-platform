"""Deterministic performance digest from observed data only.

Generates concise factual statements based strictly on computed
metric comparisons. Never implies causality, never generates
statements when comparison data is missing, and never uses
AI to invent interpretations.
"""

from dataclasses import dataclass


def _pct_text(name: str, pct: float) -> str | None:
    """Format a percentage change statement deterministically."""
    abs_pct = abs(pct)
    if abs_pct < 1.0:
        return f"{name} was essentially unchanged compared with the previous period."
    direction = "increased" if pct > 0 else "decreased"
    return f"{name} {direction} {abs_pct:.1f}% compared with the previous period."


@dataclass(frozen=True, slots=True)
class ReportingDigest:
    """Produce deterministic, data-backed performance summary."""

    @staticmethod
    def digest(
        ga4_metrics: dict[str, dict[str, object]],
        gsc_metrics: dict[str, dict[str, object]],
    ) -> list[str]:
        """Return factual statements based strictly on observed data.

        Only generates statements when both current and previous values
        exist and the percent change is meaningful. Returns empty list
        when no supported statements can be made.
        """
        statements: list[str] = []

        # GA4 metrics
        ga4_label_map = {
            "ga4.sessions": "Sessions",
            "ga4.totalUsers": "Users",
            "ga4.screenPageViews": "Page views",
            "ga4.conversions": "Conversions",
        }
        for key, label in ga4_label_map.items():
            metric = ga4_metrics.get(key, {})
            pct = metric.get("percent_delta")
            if pct is not None and isinstance(pct, (int, float)):
                stmt = _pct_text(label, float(pct))
                if stmt is not None:
                    statements.append(stmt)

        gsc_label_map = {
            "clicks": "Search clicks",
            "impressions": "Search impressions",
            "ctr": "Click-through rate",
            "position": "Average search position",
        }
        for key, label in gsc_label_map.items():
            metric = gsc_metrics.get(key, {})
            pct = metric.get("percent_delta")
            if pct is not None and isinstance(pct, (int, float)):
                stmt = _pct_text(label, float(pct))
                if stmt is not None:
                    statements.append(stmt)

        return statements
