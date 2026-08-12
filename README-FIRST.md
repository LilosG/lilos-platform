# LILOs OpenCode Finish-Line Setup

This package turns OpenCode into a controlled release environment for the LILOs platform.

## Important

Do not start multiple coding agents immediately.

The sequence is:

1. Start from a clean, current `main`.
2. Create `release/platform-consolidation` before committing any setup files.
3. Install these files in the root of `lilos-platform`.
4. Confirm the included governing documents under `docs/governing/`.
5. Create a dedicated OpenRouter API key with a hard spending cap.
6. Run Round 0 with `release-integrator`.
7. Execute Packet 1 (platform information architecture) with the principal agent.
8. Only after Packet 1 is accepted, create isolated Git worktrees and parallelize integrations, automation, and product UX.
9. Run `release-auditor` after every packet.
10. The principal agent alone integrates specialist branches and updates the release ledger.
11. Insights/reporting runs after the shared product/integration contracts are stable.
12. Run the full release gate once at the end, after focused verification during development.

## Governing documents included

The package already contains the reviewed project documents at these exact paths:

- `docs/governing/LILOS-MASTER-SPEC.md`
- `docs/governing/LILOS-BUILD-ROADMAP.md`
- `docs/governing/LILOS-MASTER-BUILD-PROMPT.md`
- `docs/governing/LILOS-FINISH-LINE-HANDOFF.md`

The repository itself remains the source of truth for what is currently implemented. Historical chats are evidence only.

## Model policy

Default implementation model:
`openrouter/deepseek/deepseek-v4-pro`

Read-only auditor:
`openrouter/deepseek/deepseek-v4-flash`

Do not rotate models casually. If a packet fails acceptance twice for the same evidence-backed defect, escalate only that defect to a stronger model or an independent second analysis.

## Branch policy

- `main` remains stable.
- Create `release/platform-consolidation` for the integrated V1 release.
- Specialists work in isolated worktrees/branches created from the accepted Packet 1 commit.
- Specialists do not push or merge themselves.
- The principal release integrator reviews and integrates specialist work.

## Start

Start by creating the release branch from a clean, current `main`:

```bash
git switch main
git pull --ff-only
git status
git switch -c release/platform-consolidation
```

Then install the package, verify the included governing docs, commit the control-plane setup on the release branch, and start:

```bash
opencode
```

Select the `release-integrator` primary agent and paste:

`prompts/ROUND-0-PRINCIPAL.md`

Do not start specialist worktrees before Round 0 and Packet 1 are accepted.
