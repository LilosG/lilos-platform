# Contracts package

FastAPI/Pydantic is transport authority. `openapi.json` and `src/generated/api.ts`
are committed deterministic exports; generate with `npm run contracts:generate`.
`npm run contracts:check` regenerates in isolation and compares bytes, including
new/untracked artifacts. CI rejects drift. Internal/tool endpoints are excluded.

Console server transports and adapters consume generated schemas. Operational UI
uses tested projections; canonical domain mutation routes remain authoritative.
