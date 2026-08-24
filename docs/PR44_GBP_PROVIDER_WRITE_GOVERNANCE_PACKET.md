# PR44 — GBP Provider Write Governance + Google Workspace Operational UX

## Objective

Complete the next production acceptance slice for Google Business Profile without creating a one-off bypass.

LILOs already has:
- a confirmed GBP mapping;
- a canonical AAL2-protected mapping confirmation endpoint;
- a `write_enabled` safety gate on `GBPLocation`;
- server-side publish/upload guards that reject provider writes unless the mapping is confirmed and `write_enabled=true`;
- successful production Google read/discovery/sync acceptance for Wheyland Electric.

What is missing is the **operator control-plane workflow** that lets an authorized administrator deliberately enable or disable provider writes for an already-confirmed mapping, with truthful state, auditability, and immediate UI reconciliation.

This packet is part of the larger project-wide closure effort. Do not implement a Wheyland-specific hack or a hidden manual database switch. Build the reusable platform behavior that every tenant/location will use.

---

## Production evidence / current defects

### 1. Provider writes are intentionally disabled but cannot be governed from the UI

`apps/api/app/products/gbp/contracts.py`:

```py
class MappingConfirm(BaseModel):
    location_id: UUID
    write_enabled: bool = False
```

`apps/api/app/products/gbp/service.py::confirm_mapping()` persists that flag.

`apps/api/app/routes/gbp.py` exposes the canonical mutation:

```text
POST /api/v1/organizations/{organization_id}/locations/{location_id}/gbp/locations/{gbp_location_id}/confirm
```

It is protected by `gbp.connect` at AAL2.

`apps/web/src/lib/gbp.ts::confirmLocationMapping()` already calls this exact endpoint and already accepts `writeEnabled`.

However, `apps/web/src/pages/integrations.astro` only uses mapping confirmation for an unmapped resource and does not expose write-access governance for existing mapped resources.

Result in production: Wheyland Electric is correctly mapped and fresh, but Business Profile reports **Read only** and there is no operator control to change that safely.

### 2. The Google workspace read model does not expose enough identity/state to operate the canonical mutation

`apps/api/app/integrations/directory_service.py::_confirmed_mappings()` currently returns provider mapping identity, platform resource id, display name, sync timestamp/freshness, but not:
- canonical `GBPLocation.id` (`gbp_location_id`);
- `GBPLocation.write_enabled`;
- `GBPLocation.mapping_status`.

The Integrations UI therefore cannot render or govern the real write state from its provider workspace read model.

### 3. Successful discovery leaves stale UI until a page reload

Current `integrations.astro` changes the discovery button text after success but does not re-fetch the Google workspace. Production acceptance required a manual browser reload to observe `Stale -> Fresh`.

This is not acceptable operational UX. A successful mutation/read-refresh action must reconcile the visible provider workspace from backend truth.

### 4. Unmapped queue identity is inconsistent with the canonical mapping identity

In `apps/api/app/routes/integrations.py::google_unmapped()`, `ProviderResourceMapping.platform_resource_id` values are collected, but the loop compares those platform `Location.id` values against `GBPLocation.id`:

```py
if loc.id in mapped_ids:
    continue
```

`platform_resource_id` is the platform `Location.id`; the corresponding GBP row field is `GBPLocation.location_id` (or its canonical integration-resource relationship), not `GBPLocation.id`.

Fix this while touching the same control-plane surface so a mapped GBP location cannot leak back into the privileged unmapped queue.

---

## Required architecture

### A. Keep one canonical write-access mutation

Do **not** add a duplicate Integrations-owned mutation route.

Use the existing canonical AAL2 GBP confirmation endpoint via `confirmLocationMapping()` for both:
- initial mapping confirmation (default read-only), and
- explicit write-access enable/disable on an existing confirmed mapping.

The Integrations page is the control-plane UI; the GBP product route remains the domain mutation owner.

### B. Read model must expose canonical operating identity

Extend each mapped Google location resource to include, for `resource_type == "location"` when resolvable:

```text
gbp_location_id: string | null
mapping_status: string | null
write_enabled: boolean | null
```

Keep existing fields:

```text
id  # ProviderResourceMapping.id
external_resource_id
platform_resource_id
resource_type
status
display_name
last_synced_at
sync_freshness
```

Never infer `write_enabled` from OAuth scope or provider capability. It is a LILOs governance flag and must come from the resolved tenant-scoped `GBPLocation` row.

### C. Mapped-resource operator UX

For a mapped GBP location with:
- `resource_type == "location"`;
- non-null `platform_resource_id`;
- non-null `gbp_location_id`;
- `mapping_status == "confirmed"`;

render truthful write-access state:

- badge/text: **Read only** when `write_enabled=false`;
- badge/text: **Provider writes enabled** when `write_enabled=true`.

For platform administrators, provide one deliberate action:

- when read-only: **Enable provider writes**;
- when enabled: **Disable provider writes**.

The action must:
1. show an inline confirmation before mutation;
2. explain the consequence accurately;
3. call `confirmLocationMapping(organizationId, platform_resource_id, gbp_location_id, desiredWriteEnabled)`;
4. rely on the canonical endpoint's AAL2 + authorization handling;
5. on success, re-fetch the Google workspace and re-render from backend truth;
6. on failure, restore the action and show the normal safe error UI;
7. never locally fake the final write state.

Suggested confirmation copy:

Enable:
> Enable provider writes for this Business Profile location? Approved LILOs workflows will be allowed to publish supported changes to Google. Human approval, workflow, audit, and provider verification controls still apply.

Disable:
> Disable provider writes for this Business Profile location? Existing Google data remains unchanged, but new LILOs provider-write operations will be blocked until writes are enabled again.

Do not automatically publish anything when writes are enabled.

### D. Improve mapping audit semantics

`GBPService.confirm_mapping()` currently records `gbp.location.mapping_confirmed` every time the canonical endpoint is used.

Make its audit truthfully distinguish a confirmed mapping's write-access change from an actual mapping confirmation/remap.

Required behavior:
- capture prior `location_id`, `mapping_status`, and `write_enabled` before mutation;
- if an already-confirmed mapping remains on the same platform location and only `write_enabled` changes, audit `gbp.location.write_access_changed` with metadata containing prior and new values;
- otherwise keep `gbp.location.mapping_confirmed` for mapping confirmation/remap semantics;
- an idempotent repeat with no state change must not falsely claim a write-access change. It may retain a mapping-confirmed/upsert audit only if that is already the canonical service behavior, but do not emit `write_access_changed` unless the boolean actually changed.

Do not weaken or remove the existing provider-resource mapping audit.

### E. Reconcile Google workspace immediately after discovery

After `discoverResources()` succeeds, do not only update button text.

Re-fetch:
- connection status if needed for accurate token verification timestamp;
- `fetchGoogleWorkspace()`;

then re-render the Google provider workspace so:
- `last_verified_at` / token state are current;
- mapped freshness is current;
- unmapped count is current;
- write-access controls are current.

Avoid recursive duplicate requests or stale captured `connectionResult` state. Implement a clean provider-workspace reload function if needed.

### F. Fix unmapped-resource identity

Correct `google_unmapped()` so an already mapped GBP row is excluded using canonical identity.

At minimum, compare mapped platform ids to `loc.location_id`, not `loc.id`.

Prefer the same mapping identity model already used by `IntegrationDirectoryService._confirmed_mappings()` where practical. Preserve organization and connection scoping.

Do not broaden provider enumeration to ordinary product users.

---

## Server-side safety invariants that must remain

Do not modify away these existing gates:

- initial mappings remain `write_enabled=False` unless an authorized operator explicitly enables writes;
- `GBPOperationsService` must continue blocking post/media provider writes when `write_enabled` is false or mapping is not confirmed;
- approval is still required before publish-eligible operations;
- workflow-run consumption/idempotency remains required;
- provider calls remain outside long-held database locks;
- provider result verification/reconciliation remains required;
- Google OAuth scopes do not imply LILOs write authorization;
- no tenant can operate another tenant's mapping/location;
- no raw Google tokens/secrets are exposed to the web client;
- no automatic publish occurs as a side effect of enabling writes.

---

## Required tests

Add focused deterministic regression coverage, not shallow source-string assertions where behavior can be exercised.

### Python / backend

1. `_confirmed_mappings()` returns the resolved `gbp_location_id`, `mapping_status`, and `write_enabled` from the correct organization-scoped GBP row.
2. Read-only mapped resource reports `write_enabled=False`.
3. Write-enabled mapped resource reports `write_enabled=True`.
4. A provider mapping that cannot resolve a GBP location returns safe null governance fields, not invented state.
5. Write-access false -> true through `confirm_mapping()` persists true and records truthful audit metadata/event.
6. Write-access true -> false persists false and records truthful audit metadata/event.
7. Idempotent same-value confirmation does not emit a false `write_access_changed` event.
8. Existing tenant/location scope and AAL2 route contract remain intact.
9. `google_unmapped()` excludes a GBP location whose `location_id` is already in active provider mappings.
10. An actually unmapped GBP location remains in the queue.

### Web / frontend

Cover the reusable behavior at the lowest reliable level supported by the repo:

1. `MappedResource` contract includes `gbp_location_id`, `mapping_status`, `write_enabled`.
2. mapped-resource UI renders **Enable provider writes** for read-only confirmed mappings.
3. mapped-resource UI renders **Disable provider writes** for write-enabled confirmed mappings.
4. action uses `confirmLocationMapping()`; do not duplicate the route string in `integrations.astro`.
5. successful action re-fetches/re-renders workspace truth.
6. successful discovery re-fetches/re-renders workspace truth instead of requiring page reload.
7. ordinary/non-admin views do not receive the privileged write-governance action.

If browser fixtures make a full interaction test straightforward, add one. Do not build a giant new test harness only for this packet.

---

## Scope exclusions

Do not in this packet:
- publish a real Google post;
- change post copy/generation logic;
- change Hermes routing/runtime;
- change SEO/GSC/GA4 logic;
- change Reviews, Leads, Content, onboarding, billing, or unrelated navigation;
- add a second GBP mapping/write endpoint;
- bypass AAL2;
- weaken human approval or provider verification;
- modify Google OAuth scopes;
- auto-enable writes for all existing mappings.

This packet enables the governed control needed for the **next live acceptance step**. The actual controlled provider write happens only after this code is merged/deployed and the operator explicitly enables writes for Wheyland Electric.

---

## Validation discipline

Use the repository's established process:

1. inspect the owning files and current tests;
2. implement the complete root-cause set above as one coherent batch;
3. run narrow formatting/lint/type checks and focused GBP/Integrations/web tests;
4. fix focused failures from evidence;
5. once focused checks are green, run the repository-required integrated/release validation **one time**;
6. if that final integrated validation exposes an unrelated failure, stop and report it rather than entering a full-suite loop.

Never rerun an unchanged failing command.

---

## Acceptance after merge/deploy

Production acceptance for this packet is:

1. Integrations -> Google shows Wheyland Electric as Fresh.
2. Mapped resource visibly shows **Read only** plus **Enable provider writes** for an authorized admin.
3. Operator clicks Enable provider writes and confirms.
4. Canonical AAL2 mutation succeeds.
5. Integrations immediately reconciles and shows **Provider writes enabled** without manual reload.
6. Business Profile location view also reports **Provider writes enabled**.
7. No Google content was published merely by enabling writes.
8. Audit/history contains the truthful write-access change.

Only after those pass do we proceed to a controlled, professionally valid GBP post generation -> human approval -> real provider publish -> Google verification/reconciliation test.
