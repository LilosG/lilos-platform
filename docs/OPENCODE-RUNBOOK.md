# OpenCode Runbook — Exact Operating Procedure

## 1. Cost control before coding

Use a dedicated OpenRouter API key for this release, not a general-purpose unlimited key.

Set a hard spending limit you are comfortable losing to a runaway session. A practical starting cap is $50 total; raise it only after accepted packet gates if needed.

Keep implementation on DeepSeek V4 Pro and auditing on V4 Flash. Do not model-hop because one response is imperfect.

## 2. Create the release branch before installing anything

From the LILOs repository root:

```bash
git switch main
git pull --ff-only
git status
git switch -c release/platform-consolidation
```

If `git status` is not clean, stop and resolve the existing work first. Do not discard it.

## 3. Install the package

From the LILOs repository root, copy in:

- `AGENTS.md`
- `opencode.json`
- `.opencode/agents/`
- `docs/PLATFORM-CONSOLIDATION-RELEASE.md`
- `docs/PLATFORM-RELEASE-LEDGER.md`
- `docs/VISUAL-UX-REFERENCE-NOTES.md`
- `prompts/`
- `scripts/create-release-worktrees.sh`

The four reviewed governing docs are already included under `docs/governing/`. Verify they are present before starting Round 0.

## 4. Verify OpenCode/OpenRouter

Run:

```bash
opencode --version
opencode models | grep -E 'deepseek-v4-(pro|flash)|qwen3-coder-next'
```

If OpenRouter is not connected, launch OpenCode and use `/connect`, choose OpenRouter, and enter the dedicated release key.

Inside OpenCode, `/models` should show the configured models.

## 5. Commit only the control-plane setup

Before implementation:

```bash
git status
git add AGENTS.md opencode.json .opencode docs/PLATFORM-CONSOLIDATION-RELEASE.md docs/PLATFORM-RELEASE-LEDGER.md docs/VISUAL-UX-REFERENCE-NOTES.md docs/governing prompts scripts/create-release-worktrees.sh
git commit -m "chore: add controlled platform consolidation workflow"
```

If the governing docs should remain uncommitted for policy/repository-size reasons, do not invent a substitute; point `AGENTS.md` to their approved location and make that explicit.

The commit above must be on `release/platform-consolidation`, not `main`.

## 6. Round 0

Start:

```bash
opencode
```

Use Tab until the primary agent is `release-integrator`.

Paste the entire contents of `prompts/ROUND-0-PRINCIPAL.md`.

Do not permit product-code changes during Round 0.

Review the resulting:
- ownership map;
- packet plan;
- updated release ledger.

The principal must reconcile repository truth, not merely restate the release spec.

## 7. Packet 1

In the same release branch and principal agent, paste:

`prompts/PACKET-1-IA.md`

Allow implementation only within Packet 1.

When it claims completion, manually invoke:

`@release-auditor Review Packet 1 against AGENTS.md, the release spec, the Packet 1 prompt, current diff, tests, and release ledger. Return ACCEPT or REJECT only with evidence.`

If REJECT, give the rejection back to `release-integrator` and correct only failed acceptance criteria.

After ACCEPT, commit Packet 1.

## 8. Create parallel worktrees

Only after Packet 1 is accepted:

```bash
bash scripts/create-release-worktrees.sh
```

You now have isolated directories for:
- integrations;
- automation;
- product UX.

Open a separate terminal in each.

## 9. Run specialist agents

In each worktree:

```bash
opencode
```

Use Tab to select the corresponding primary agent.

Do not hand the specialist the whole release. The principal's `PLATFORM-PACKET-PLAN.md` must provide the bounded execution packet, owned files/contracts, and acceptance criteria.

Specialists do not merge or push.

## 10. Audit every specialist branch

At completion in that worktree:

`@release-auditor Review this execution packet and current branch diff. Try to reject it against the packet acceptance criteria and AGENTS.md.`

Correct only acceptance failures.

Commit the accepted specialist packet to its branch.

## 11. Principal integrates

Return to the main release worktree.

The principal reviews each branch before merge/cherry-pick. It checks:
- shared contract compatibility;
- architecture boundaries;
- tests;
- tenant/security behavior;
- release ledger;
- auditor evidence.

Integrate one accepted packet at a time and run focused cross-workstream regression checks.

## 12. Reporting wave

Do not begin full Insights/Reporting productization until the principal confirms integration/product/automation data contracts are stable.

Create a separate reporting worktree at that point and use `insights-reporting`.

## 13. Cost escalation rule

Do not solve model weakness by rerunning entire packets repeatedly.

Escalate when:
- the same acceptance defect survives two evidence-based corrections; or
- two analyses disagree about a high-risk root cause; or
- a cross-system production defect remains unproven after local tracing.

Escalate only the isolated defect to a stronger model/second opinion. Return the result to the V4 Pro principal.

## 14. Final gate

During development use focused tests.

On the integrated release candidate, run the complete repository/release/production acceptance gates once. Re-run only the failed portion plus the final gate after correction.

Do not call the platform complete until the release ledger reflects the agreed controlled-pilot acceptance state.
