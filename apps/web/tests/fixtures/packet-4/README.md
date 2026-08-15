# Packet 4 visual fixtures

These fixtures exist only to render Packet 4 screenshot evidence. They model
the existing TypeScript response contracts in `apps/web/src/lib`; they do not
write to a database or create provider state.

The evidence server is gated by `LILOS_PACKET4_FIXTURES=1`, binds only to
`127.0.0.1`, and proxies an explicitly started Astro development server. No
production module imports this directory, and Astro does not include files
under `apps/web/tests` in a deployed build.

Run it locally, after starting Astro on port 4321, with:

```sh
LILOS_PACKET4_FIXTURES=1 node --experimental-strip-types apps/web/tests/fixtures/packet-4/evidence-server.mjs
```

Playwright uses `visual-server.mjs` to own that Astro process and the evidence
proxy as one test-only lifecycle. The same explicit environment gate applies.

Every proxied HTML page receives a visible “Fixture-rendered acceptance
evidence · not live data” caption. The server exits immediately when the gate
environment variable is absent.
