"""The prompt for the two prose sections of a client report.

The model is handed the stored snapshot's numbers as evidence and may state only those numbers.
The checks that enforce this run in code after the draft returns (``reports.narrative``); the
prompt only asks for what the checks will accept.
"""

from __future__ import annotations

import json
from typing import Any

_RULES = (
    "You write two short sections and a few result cards of a performance report covering one "
    "or more whole months, that a local business owner will read: what changed and why it "
    "matters, and what happens next.",
    "EVIDENCE below is the only source of truth. State a number only if it appears in EVIDENCE, "
    "written the same way (a rounded whole number of the same figure is fine). Never add, "
    "subtract, average or otherwise compute a new number, and never invent a figure.",
    "Write every number with digits, never as words.",
    "If a figure is missing, partial or marked unavailable, say it is not available yet. "
    "Never guess it and never treat it as zero.",
    "Do not claim that one thing caused another. The evidence shows what moved and what was "
    "done, not why. Use cautious wording such as 'coincided with', 'may reflect' or 'we will keep "
    "watching'.",
    "Never say who or what wrote this text. Do not mention AI, assistants, models, software, "
    "tools or any company or product name.",
    "Plain language for a business owner. No jargon, no headings, no bullet characters, no "
    "emojis. what_changed is two or three short paragraphs; next_work is three to five short "
    "sentences or one short paragraph.",
    "next_work proposes sensible next steps that follow from the evidence. Do not promise "
    "results or specific numbers.",
    "result_cards is a list of up to four results for the top of the report, chosen from "
    "EVIDENCE.result_figures. Each card has: figure_keys (one or two keys from result_figures, "
    "exactly as written), tone ('good' only if that figure went up, 'bad' only if it went down, "
    "otherwise 'neutral'), headline (true for at most one card, the result that matters most), "
    "title (two to five plain words naming the result, for example 'More online reservations'), "
    "and text (one plain sentence on what happened and why it matters to the owner). Numbers in "
    "a card's text must come from that card's own figure_keys. Lead with what improved, but if "
    "nothing improved say so honestly with a neutral or bad card; never invent a win. If "
    "result_figures is empty, return an empty list.",
)


def build_report_narrative_prompt(input_document: dict[str, Any]) -> str:
    evidence = input_document.get("evidence", {})
    return "\n".join(
        [
            *_RULES,
            f"\nEVIDENCE (JSON):\n{json.dumps(evidence, default=str, sort_keys=True)}",
            "\nReturn ONLY a JSON object with the keys 'what_changed' and 'next_work' (strings) "
            "and 'result_cards' (a list).",
        ]
    )


_TOPIC_RULES = (
    "You group a local business's Google searches into topics for its monthly report. "
    "EVIDENCE lists searches that do not contain the business name, with their impressions "
    "and clicks.",
    "Make between 4 and 8 topics a business owner would recognise, such as 'Private events', "
    "'Happy hour' or 'Brunch'. A label is one to four plain words.",
    "Place each search in at most one topic, copied exactly as written in EVIDENCE. Leave a "
    "search out if it fits no topic. Do not invent searches.",
    "Some searches may be misspellings or variants of the business name itself. List those "
    "under brand_variants, copied exactly, and do not place them in a topic.",
)


def build_report_topics_prompt(input_document: dict[str, Any]) -> str:
    evidence = input_document.get("evidence", {})
    return "\n".join(
        [
            *_TOPIC_RULES,
            f"\nEVIDENCE (JSON):\n{json.dumps(evidence, default=str, sort_keys=True)}",
            "\nReturn ONLY a JSON object with the keys 'topics' (a list of objects with 'label' "
            "and 'queries') and 'brand_variants' (a list of searches).",
        ]
    )
