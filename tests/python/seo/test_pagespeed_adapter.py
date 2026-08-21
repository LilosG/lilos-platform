"""Focused tests for PageSpeed evidence normalization."""

from typing import Any, cast

from apps.api.app.products.seo.pagespeed import PageSpeedService


def test_pagespeed_summary_normalizes_scores_and_metrics() -> None:
    payload: dict[str, Any] = {
        "lighthouseResult": {
            "finalUrl": "https://example.com/",
            "fetchTime": "2026-08-21T20:00:00Z",
            "categories": {
                "performance": {"score": 0.81},
                "accessibility": {"score": 0.96},
                "best-practices": {"score": 0.92},
                "seo": {"score": 0.99},
            },
            "audits": {
                "largest-contentful-paint": {
                    "displayValue": "2.7 s",
                    "numericValue": 2700,
                    "score": 0.75,
                }
            },
        },
        "loadingExperience": {
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {
                    "category": "AVERAGE",
                    "percentile": 2600,
                }
            }
        },
    }

    result = PageSpeedService._summarize(payload)
    scores = cast(dict[str, int | None], result["scores"])
    lab_metrics = cast(dict[str, dict[str, object]], result["lab_metrics"])
    field_metrics = cast(dict[str, dict[str, object]], result["field_metrics"])

    assert scores == {
        "performance": 81,
        "accessibility": 96,
        "best-practices": 92,
        "seo": 99,
    }
    assert lab_metrics["largest_contentful_paint"]["numeric_value"] == 2700
    assert field_metrics["LARGEST_CONTENTFUL_PAINT_MS"]["category"] == "AVERAGE"
