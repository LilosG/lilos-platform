"""Builds long-form drafts of an exact word count for floor and link tests."""

import re

WORD = re.compile(r"\b[\w'-]+\b")

INVENTORY_ROWS = [
    {"url": "/menu/", "title": "Menu"},
    {"url": "/reservations/", "title": "Reservations"},
    {"url": "/locations/san-diego/", "title": "San Diego"},
    {"url": "/blog/packers-fans-guide/", "title": "Packers fans guide", "source": "content"},
    {"url": "/about/", "title": "About"},
]
LINKS = [
    "[our full food and drink menu](/menu/)",
    "[reserve a table for kickoff](/reservations/)",
    "[the San Diego bar location](/locations/san-diego/)",
    "[our Packers fans guide](/blog/packers-fans-guide/)",
]
FAQS = [
    {"question": f"Question number {i}?", "answer": " ".join(["helpful"] * 24)} for i in range(4)
]


def build_draft(*, words: int, links: list[str] | None = None, h2s: int = 8) -> str:
    """A draft with exactly `words` tokens, `h2s` sections and the given markdown links."""
    links = LINKS if links is None else links
    headings = [f"## Packers game day topic number {n}" for n in range(h2s)]
    link_paragraph = "Plan around " + ", ".join(links) + "."
    skeleton_words = len(WORD.findall("\n\n".join([*headings, link_paragraph])))
    filler_needed = words - skeleton_words
    assert filler_needed > 0
    per_section = filler_needed // h2s
    extra = filler_needed - per_section * h2s
    blocks = [link_paragraph]
    for index, heading in enumerate(headings):
        count = per_section + (1 if index < extra else 0)
        # Distinct words keep the repeated-paragraph check from firing.
        body = " ".join(f"detail{index}x{n}" for n in range(count))
        blocks.append(f"{heading}\n\n{body}")
    draft = "\n\n".join(blocks)
    assert len(WORD.findall(draft)) == words
    return draft
