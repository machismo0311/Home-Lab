#!/usr/bin/env bash
# Run the NetFRAME managed-runtime provenance verifier and emit one JSON object for the daily
# hardening drift report. Detection only: this never repairs, redeploys, switches a symlink or
# restarts a service, and there is deliberately no code path here that could.
#
# WHY IT LIVES IN HOME-LAB AND THE VERIFICATION DOES NOT. Home-Lab owns scheduling: when a check
# runs, under what timeout, and where its report goes. NetFRAME owns truth: the trust root, the
# signed manifests, the declared intended versions and the drift classes. So this script decides
# nothing about an artifact - it invokes `./netframe provenance managed --json`, bounds it, and
# hands the result to provenance_report.py to be shaped for the report.
#
# WHY A PINNED CHECKOUT. The verifier runs from the deployment checkout that the other scheduled
# NetFRAME units already use (~/.local/share/netframe/deploy), which is advanced deliberately to a
# published SHA. It is NOT the operator worktree, which moves whenever somebody is working, and it
# is NOT fetched here: a daily check that git-pulls would make its own correctness depend on GitHub
# being reachable at 06:30, and would let an unreviewed commit change what "verified" means.
#
# WHY A DATA-ONLY TEST SEAM. Tests need controlled verifier results, so NETFRAME_PROVENANCE_FIXTURE
# supplies recorded verifier OUTPUT - data, never a command to run. A fixture run is stamped
# fixture:true in its own report so it can never be mistaken for a measurement of the estate.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
transformer="${here}/provenance_report.py"

deploy="${NETFRAME_DEPLOY:-${HOME}/.local/share/netframe/deploy}"
timeout_s="${NETFRAME_PROVENANCE_TIMEOUT:-300}"
expected="${NETFRAME_PROVENANCE_EXPECTED:-2}"
fixture="${NETFRAME_PROVENANCE_FIXTURE:-}"

if [[ -n "${fixture}" ]]; then
	rc="${NETFRAME_PROVENANCE_FIXTURE_RC:-0}"
	out="$(cat -- "${fixture}" 2>/dev/null)"
	printf '%s' "${out}" | python3 "${transformer}" "${rc}" "${expected}" --fixture
	exit 0
fi

if [[ ! -x "${deploy}/netframe" ]]; then
	# Fail closed and say why. An absent verifier is UNKNOWN, never a clean bill of health.
	printf '' | python3 "${transformer}" 127 "${expected}"
	exit 0
fi

# Bounded. A verification that can hang is a scheduler that silently stops reporting.
out="$(cd "${deploy}" && timeout "${timeout_s}" ./netframe provenance managed --json 2>/dev/null)"
rc=$?

printf '%s' "${out}" | python3 "${transformer}" "${rc}" "${expected}"
