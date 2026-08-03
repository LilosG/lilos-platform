# Phase 10 Route Authorization Matrix

| Operation | Permission | AAL | Scope |
|---|---|---|---|
| List/read reviews and response history | `reviews.read` | aal1 | location |
| Generate/manual draft | `reviews.generate_response` | aal1 | location |
| Approve/reject response | `reviews.approve_response` | aal2 | location |
| Reserve provider publication | `reviews.publish_response` | aal2 | location |
| Restricted escalation | `reviews.escalate` | aal2 | location |
