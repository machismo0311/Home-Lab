#!/usr/bin/env bash
# REGISTRY CERTIFICATE REISSUE & SERVICE RESTORATION V1
#
# Re-issues the expired registry.netframe.local leaf ONCE, using the EXISTING
# JWK provisioner (admin@netframe.local) on the EXISTING NetFRAME Internal CA.
# Nothing is rotated, replaced or created: same CA, same provisioner, same
# hostname, same SANs, same CA-default lifetime.
#
# Secret handling:
#   - the provisioner password is never read, printed or transmitted; step is
#     pointed at the file path step-ca itself already uses
#   - NO bearer token exists anywhere: `step ca sign` mints and consumes its own
#     one-time token internally on pve2, so no token reaches argv, a Secret,
#     a log, or this workstation
#   - the TLS private key is generated inside the cluster and never leaves it;
#     only the CSR (out) and the signed chain (in) cross the boundary, both of
#     which are public material
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
JOB_YAML="${JOB_YAML:-$HERE/40-cert-reissue.yaml}"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config-rke2}"
export PATH="$HOME/.local/bin:$PATH"
K="kubectl -n registry"

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
CSR="$WORK/tls.csr"; CRT="$WORK/tls.crt"; ROOT="$WORK/root.crt"

say() { printf '\n=== %s\n' "$*"; }

say "0. preflight  ($(date -u +%FT%TZ))"
$K get cronjob registry-cert-renew >/dev/null
$K get cm netframe-root-ca         >/dev/null
$K get sa registry-cert-renewer    >/dev/null
$K get secret registry-tls         >/dev/null
test -f "$JOB_YAML"
$K get job registry-cert-reissue >/dev/null 2>&1 && { echo "a reissue Job already exists - refusing"; exit 1; }
$K get cm netframe-root-ca -o jsonpath='{.data.root\.crt}' > "$ROOT"
echo "ok"

say "1. start the in-cluster key/CSR generation Job"
$K apply -f "$JOB_YAML"
for i in $(seq 1 60); do
  POD="$($K get pod -l job-name=registry-cert-reissue -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
  [ -n "${POD:-}" ] && break
  sleep 2
done
[ -n "${POD:-}" ] || { echo "no pod appeared"; exit 1; }
echo "pod: $POD"

say "2. wait for CSR_READY"
for i in $(seq 1 90); do
  if $K logs "$POD" -c gen 2>/dev/null | grep -q CSR_READY; then echo "CSR ready"; break; fi
  if [ "$i" -eq 90 ]; then
    echo "gen container never signalled CSR_READY"
    $K logs "$POD" -c gen || true
    $K describe pod "$POD" | sed -n '/Events:/,$p' || true
    exit 1
  fi
  sleep 2
done

say "3. read the CSR out of the pod (public material)"
$K exec "$POD" -c gen -- cat /work/tls.csr > "$CSR"
openssl req -in "$CSR" -noout -verify
openssl req -in "$CSR" -noout -subject
openssl req -in "$CSR" -noout -text | sed -n '/Subject Alternative Name/{n;p;}'

say "4. sign the CSR on pve2 with the existing JWK provisioner"
# step ca sign mints its own single-use token internally; neither the token nor
# the password ever appears in argv, output, or on this workstation.
scp -q -o BatchMode=yes "$CSR" pve2:/tmp/registry-reissue.csr
ssh -o BatchMode=yes pve2 "rm -f /tmp/registry-reissue.crt; \
  STEPPATH=/etc/step-ca step ca sign /tmp/registry-reissue.csr /tmp/registry-reissue.crt \
    --provisioner 'admin@netframe.local' \
    --provisioner-password-file /etc/step-ca/secrets/password \
    --ca-url https://ca.netframe.local \
    --root /etc/step-ca/certs/root_ca.crt"
scp -q -o BatchMode=yes pve2:/tmp/registry-reissue.crt "$CRT"
ssh -o BatchMode=yes pve2 "rm -f /tmp/registry-reissue.csr /tmp/registry-reissue.crt"
echo "signed; pve2 scratch removed"

say "5. validate the signed chain BEFORE injecting it (all public material)"
N=$(grep -c 'BEGIN CERTIFICATE' "$CRT"); echo "chain length: $N"; [ "$N" -eq 2 ]
openssl x509 -in "$CRT" -noout -subject -issuer -serial -dates
openssl x509 -in "$CRT" -noout -ext subjectAltName
# the signed cert must carry the public key of the CSR the pod generated
A=$(openssl x509 -in "$CRT" -noout -pubkey | openssl md5)
B=$(openssl req  -in "$CSR" -noout -pubkey | openssl md5)
[ "$A" = "$B" ] && echo "public key matches the in-cluster CSR: OK" || { echo "PUBLIC KEY MISMATCH"; exit 1; }
awk 'BEGIN{n=0} /BEGIN CERTIFICATE/{n++} n==2' "$CRT" > "$WORK/int.crt"
openssl verify -CAfile "$ROOT" -untrusted "$WORK/int.crt" "$CRT"

say "6. inject the signed chain into the pod (atomic)"
$K exec -i "$POD" -c gen -- sh -c 'cat > /work/tls.crt.part && mv /work/tls.crt.part /work/tls.crt' < "$CRT"
echo "injected"

say "7. wait for the Job to install the Secret and roll the registry"
$K wait --for=condition=complete job/registry-cert-reissue --timeout=300s || {
  echo "JOB DID NOT COMPLETE"; $K logs "$POD" -c gen || true; $K logs "$POD" -c apply || true; exit 1; }
$K logs "$POD" -c gen
$K logs "$POD" -c apply
$K rollout status deploy/registry --timeout=300s

say "8. ACCEPTANCE - certificate now in secret/registry-tls (public bytes)"
$K get secret registry-tls -o jsonpath='{.data.tls\.crt}' | base64 -d \
  | openssl x509 -noout -subject -issuer -serial -dates -ext subjectAltName
echo "secret keys: $($K get secret registry-tls -o go-template='{{range $k,$v := .data}}{{$k}} {{end}}')"
echo "secret type: $($K get secret registry-tls -o jsonpath='{.type}')"
echo "resourceVersion: $($K get secret registry-tls -o jsonpath='{.metadata.resourceVersion}')"

say "9. ACCEPTANCE - certificate actually served on 192.168.10.72:443"
echo | openssl s_client -connect registry.netframe.local:443 \
        -servername registry.netframe.local 2>/dev/null \
  | openssl x509 -noout -subject -serial -dates -ext subjectAltName

say "10. ACCEPTANCE - trust-validating client (expect ssl_verify_result=0)"
curl -sS --cacert "$ROOT" https://registry.netframe.local/v2/ \
     -o /dev/null -w 'http=%{http_code} ssl_verify_result=%{ssl_verify_result}\n'

say "11. cleanup"
$K delete job/registry-cert-reissue --ignore-not-found
$K get cronjob registry-cert-renew

echo
echo "DONE at $(date -u +%FT%TZ). The next scheduled registry-cert-renew run"
echo "(0 */8 * * * UTC) will authenticate with the valid leaf and succeed."
