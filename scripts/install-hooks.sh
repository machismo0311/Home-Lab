#!/usr/bin/env bash
# Point git at the repo's tracked hooks (.githooks/) so the pre-commit
# secret scanner runs on every commit. Re-run after a fresh clone.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true
echo "✓ core.hooksPath -> .githooks (pre-commit secret scan active)"
