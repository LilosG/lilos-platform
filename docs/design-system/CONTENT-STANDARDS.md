# LILOs content standards

These standards govern customer-facing interface copy. Raw backend values are
never presentation language. The canonical status conversion remains
`apps/web/src/lib/status-language.ts`; action, empty-state, and error structures
are encoded in `apps/web/src/lib/ui/content.ts`.

## Status vocabulary

Use the narrowest accurate term:

| Term | Meaning |
| --- | --- |
| Ready | Setup is complete and work can begin. |
| Active | A product, workflow, or schedule is enabled. |
| Connected | Provider authorization is currently available. |
| Mapped | A provider resource is assigned to a LILOs resource. |
| Synced | Data was successfully refreshed; include freshness separately. |
| Scheduled | Future work has a recorded execution time. |
| Draft | Work exists but has not entered approval. |
| Awaiting approval | Work requires an authorized decision. |
| Published | The publishing destination accepted the work. |
| Completed | The recorded operation finished successfully. |
| Paused | Work is intentionally suspended. |
| Needs attention | An operator action is required. |
| Not yet synced | No successful synchronization has been recorded. |
| Unavailable | The capability cannot currently be used in this context. |

Do not expose enum spellings, combine connection health with data freshness, or
use “success” as a displayed status. Color supplements the label; it never
replaces it.

## Actions

Buttons begin with a concrete verb: Open, Review, Connect, Map, Configure,
Approve, Publish, Sync, Retry, Resolve, or Save. The verb remains recognizable
through the flow: Publish → Publishing… → Published. Do not replace completion
feedback with a generic “Done” or change the object unexpectedly.

Destructive buttons name the destructive action. Navigation links do not use
“Submit.” Loading labels use an ellipsis character and controls remain disabled
until the operation resolves.

## Empty states

An empty state contains exactly:

1. One factual heading.
2. One sentence explaining the current situation without treating missing data
   as zero or a fault.
3. At most one next action.

State the invitation once per meaningful region. Do not repeat identical copy
and identical buttons across adjacent cards. If there is no action the user can
take, omit the action rather than inventing one.

## Errors

An error contains:

1. A title naming the failed operation: “Could not publish content.”
2. A factual explanation of what happened, using provider detail only when it
   is safe and useful.
3. One recovery instruction.
4. One recovery action when the interface can provide it.

Avoid “Something went wrong,” unexplained codes, blame, and promises that retry
will succeed. Permission errors direct the user to an authorized owner; setup
errors direct the user to the owning control plane.

## Operational descriptions

Describe the row’s distinguishing operational facts. Automation rows name the
schedule, last result, next run, and failure count. Repeating generic guarantees
such as “validation, permissions, audit, and recovery controls” on every row is
not useful operator content.

Metric copy states the period and source once per section. Movement uses the
correct unit and outcome direction; it is not described as a system status.
