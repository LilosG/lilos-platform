"""The prompt for the two prose sections of a monthly client report.

The model is handed the stored snapshot's numbers as evidence and may state only those numbers.
The checks that enforce this run in code after the draft returns (``reports.narrative``); the
prompt only asks for what the checks will accept.
"""

from __future__ import annotations

import json
from typing import Any

_RULES = (
    "You write two short sections of a monthly performance report that a local business owner "
    "will read: what changed and why it matters, and what happens next.",
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
)


def build_report_narrative_prompt(input_document: dict[str, Any]) -> str:
    evidence = input_document.get("evidence", {})
    return "\n".join(
        [
            *_RULES,
            f"\nEVIDENCE (JSON):\n{json.dumps(evidence, default=str, sort_keys=True)}",
            "\nReturn ONLY a JSON object with the keys 'what_changed' and 'next_work', "
            "each a string.",
        ]
    )
