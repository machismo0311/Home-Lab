#!/usr/bin/env bash
# Point git at the tracked hooks in this repo. Run once per clone.
#   ./.githooks/install-hooks.sh
# Requires the gitleaks binary on PATH (https://github.com/gitleaks/gitleaks).

cd "$(dirname "$0")/.." || exit 1
git config core.hooksPath .githooks
echo "core.hooksPath -> .githooks"

if command -v gitleaks >/dev/null 2>&1; then
	echo "gitleaks $(gitleaks version) detected; pre-commit secret scan is active."
else
	echo "note: gitleaks not on PATH yet; the hook will warn-and-skip until you install it."
fi
