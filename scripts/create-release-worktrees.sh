#!/usr/bin/env bash
set -euo pipefail

# Run from the main lilos-platform working tree AFTER Packet 1 is accepted
# and committed on release/platform-consolidation.

BASE_BRANCH="release/platform-consolidation"

git status --short
git rev-parse --verify "$BASE_BRANCH"

git worktree add ../lilos-integrations -b release/integrations "$BASE_BRANCH"
git worktree add ../lilos-automation -b release/automation "$BASE_BRANCH"
git worktree add ../lilos-product-ux -b release/product-ux "$BASE_BRANCH"

echo
echo "Created:"
git worktree list
echo
echo "Do not create the reporting worktree until the principal says data contracts are stable."
