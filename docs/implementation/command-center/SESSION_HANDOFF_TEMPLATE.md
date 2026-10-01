# LILOs Command Center — Coding Session Handoff

Use this at the end of any coding-agent session when work is not yet merged.

## Repository

`LilosG/lilos-platform`

## Branch

`<branch>`

## Base main SHA

`<sha>`

## Current HEAD

`<sha>`

## Phase

`Phase <n> — <name>`

## Completed

- <item>
- <item>

## Remaining

- <item>
- <item>

## Files changed

```text
<paths>
```

## Tests actually run

```text
<commands and results>
```

## Tests not run

```text
<explicit list>
```

## Known blockers

- <blocker>

## Owner action required

- <action or NONE>

## Important verified decisions

- <decision>

## Do not change

- Do not change `MASTER_PLAN.md` architecture unless a verified current-code conflict requires a documented decision.
- Do not begin the next phase.
- Do not merge automatically.

## Resume prompt

```text
Resume the current Command Center phase from the existing branch and working tree.

Read:
- AGENTS.md
- CLAUDE.md
- docs/implementation/command-center/MASTER_PLAN.md
- the current phase prompt
- this handoff

Verify git status and HEAD before making changes.

Continue only the remaining in-scope work.
Do not regenerate completed work.
Do not redesign unrelated screens.
Do not begin the next phase.
Run the remaining required checks before opening/updating the PR.
```
