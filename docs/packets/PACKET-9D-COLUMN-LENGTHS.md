# Packet 9D — SEO Crawl Column-Length Overflow

**Branch:** `packet/9d-column-lengths` off `main`
**Builder:** DeepSeek V4 Pro
**Depends on:** Packet 9C (lease-renewal deadlock, merged)

A live crawl of `wheylandelectric.com` aborted with `StringDataRightTruncationError`
on `INSERT INTO seo_pages`: value too long for `character varying(2000)`. Zero pages
persisted — one oversized value aborts the entire crawl.

---

## Evidence

A live crawl against `lilos_test` (schema at head `20260815_0001`) of
`wheylandelectric.com` produced, on three pages (`/contact-us/`, `/`, `/about/`):

```
OVERFLOW h1 len=3001 @ .../contact-us/
OVERFLOW h1 len=7691 @ .../
OVERFLOW h1 len=3126 @ .../about/
DBAPIError: asyncpg.exceptions.StringDataRightTruncationError:
    value too long for type character varying(2000)
```

The offending column is `h1` (3,001–7,691 characters). The `h1` value was absurd
for two reasons: the site's `<h1>` is ordinary, but the extraction used a slice
of `start + absolute_close_index` (adding an absolute index as if it were a
relative offset), capturing the entire tag-stripped page body after the first
`<h1>` instead of just the heading text. That is corrected here, and content
truncation is added as the defensive layer for genuinely absurd pages.

Seven columns were sized `varchar(2000)`.

---

## Fixes by category

### Content columns (`title`, `meta_description`, `h1`)

Stay `varchar(2000)`. Truncate at ingest to a documented limit of **2000
characters** with the marker `…[truncated]` appended (reserving room so the
stored value never exceeds the column). A `*_truncated` entry is recorded in
`technical_issues`, so truncation is observable rather than silent. Limit
chosen to match the existing column width, so no content-column schema change
is required.

### URL columns (`normalized_url`, `observed_url`, `canonical_url`, `redirect_destination`)

Widened to `text` (migration `20260817_0001`). Browsers and servers legitimately
produce URLs beyond 2000 characters, and truncating a URL corrupts a reference
used for deduplication and traversal. The crawler enforces a documented maximum
of **2048 characters** (`crawl_engine.MAX_URL_LENGTH`) instead: an over-long
page URL is recorded as skipped with reason `url_too_long`; an over-long
`canonical_url` or `redirect_destination` is dropped with a `*_too_long`
technical issue; an over-long `observed_url` falls back to the request URL.

`normalized_url` participates in `uq_seo_page_normalized_url`. Postgres limits a
btree index entry to ~2704 bytes. A 2048-character ASCII URL plus the 16-byte
`website_id` and tuple overhead stays well under that. Verified by inserting a
2051-character URL through the live index on `lilos_test`.

### Single malformed page never aborts a crawl

`persist_page` now runs each page inside its own savepoint with a try/except.
A failing page rolls back its own savepoint, is recorded in
`crawl_run.safe_result["page_failures"]`, and the crawl continues.

---

## Acceptance

1. `h1` extraction captures only the `<h1>` content, not the page body. Test.
2. Over-length `title`, `meta_description`, and `h1` truncate to 2000 with the
   marker and a `*_truncated` technical issue. Unit + database-backed test.
3. Over-length URL is skipped with `url_too_long`; over-long canonical/redirect
   omitted with a `*_too_long` issue. Test.
4. A crawl with over-length content completes `success` and persists truncated
   values; `page_failures` is empty. Database-backed test (fails on pre-fix main).
5. Migration widens URL columns to `text`; btree index accepts a >2000-char URL.
6. Full gate: `uv run ruff format --check`, `uv run ruff check`,
   `uv run mypy`, `uv run pytest` (database-backed included).

Do not commit, merge, or push.
