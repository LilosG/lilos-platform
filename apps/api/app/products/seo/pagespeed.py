"""Google PageSpeed Insights enrichment for SEO analysis.

The adapter is deliberately read-only. It returns a compact, provider-neutral
summary that can be persisted inside crawl evidence without storing the full
Lighthouse payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from apps.api.app.config import Settings

PAGESPEED_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
PAGESPEED_CATEGORIES = ("PERFORMANCE", "ACCESSIBILITY", "BEST_PRACTICES", "SEO")


@dataclass(frozen=True, slots=True)
class PageSpeedService:
    timeout_seconds: float = 45.0

    async def analyze(self, settings: Settings, url: str) -> dict[str, object] | None:
        """Return mobile/desktop Lighthouse summaries, or ``None`` when unconfigured."""
        api_key = settings.google_pagespeed_api_key
        if not api_key:
            return None

        strategies: dict[str, object] = {}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for strategy in ("mobile", "desktop"):
                params: list[tuple[str, str]] = [
                    ("url", url),
                    ("key", api_key),
                    ("strategy", strategy),
                ]
                params.extend(("category", category) for category in PAGESPEED_CATEGORIES)
                response = await client.get(PAGESPEED_ENDPOINT, params=params)
                response.raise_for_status()
                payload = response.json()
                strategies[strategy] = self._summarize(payload)
        return {"url": url, "strategies": strategies, "provider": "google_pagespeed"}

    @staticmethod
    def _summarize(payload: dict[str, Any]) -> dict[str, object]:
        lighthouse = payload.get("lighthouseResult") or {}
        categories = lighthouse.get("categories") or {}
        audits = lighthouse.get("audits") or {}
        loading = payload.get("loadingExperience") or {}
        origin_loading = payload.get("originLoadingExperience") or {}

        scores: dict[str, int | None] = {}
        for key in ("performance", "accessibility", "best-practices", "seo"):
            raw = (categories.get(key) or {}).get("score")
            scores[key] = round(float(raw) * 100) if isinstance(raw, (int, float)) else None

        audit_keys = {
            "largest_contentful_paint": "largest-contentful-paint",
            "cumulative_layout_shift": "cumulative-layout-shift",
            "interaction_to_next_paint": "interaction-to-next-paint",
            "total_blocking_time": "total-blocking-time",
            "speed_index": "speed-index",
        }
        lab_metrics: dict[str, object] = {}
        for output_key, audit_key in audit_keys.items():
            audit = audits.get(audit_key) or {}
            lab_metrics[output_key] = {
                "display_value": audit.get("displayValue"),
                "numeric_value": audit.get("numericValue"),
                "score": audit.get("score"),
            }

        return {
            "scores": scores,
            "lab_metrics": lab_metrics,
            "field_metrics": PageSpeedService._field_metrics(loading),
            "origin_field_metrics": PageSpeedService._field_metrics(origin_loading),
            "final_url": lighthouse.get("finalUrl"),
            "fetch_time": lighthouse.get("fetchTime"),
        }

    @staticmethod
    def _field_metrics(experience: dict[str, Any]) -> dict[str, object]:
        metrics = experience.get("metrics") or {}
        result: dict[str, object] = {}
        for key in (
            "LARGEST_CONTENTFUL_PAINT_MS",
            "CUMULATIVE_LAYOUT_SHIFT_SCORE",
            "INTERACTION_TO_NEXT_PAINT",
            "FIRST_CONTENTFUL_PAINT_MS",
        ):
            item = metrics.get(key)
            if isinstance(item, dict):
                result[key] = {
                    "category": item.get("category"),
                    "percentile": item.get("percentile"),
                }
        return result
