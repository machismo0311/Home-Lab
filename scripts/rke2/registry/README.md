# Private container registry (RKE2, on Randy, TLS via step-ca)

A private OCI registry (`registry:2`) running on the **Randy** storage node, backed
by a node-local PV on Randy's `datastore` ZFS, exposed via **MetalLB** at
`192.168.10.72` as **`https://registry.netframe.local`** with a **step-ca** cert
that **auto-renews** (passwordless).

See `vault/Runbook/RKE2-Phase1-HA-ControlPlane-2026-07-10.md` §Phase 6/7 for the
full story and gotchas.

## Files
| File | Contents |
|---|---|
| `10-storage.yaml` | namespace, node-local PV (`/datastore/k8s-local/registry`, pinned to `randy`), PVC |
| `20-registry.yaml` | Deployment (registry-native TLS) + Service (MetalLB LB `.72:443`) |
| `30-cert-renew.yaml` | ServiceAccount/Role/RoleBinding + CronJob (renews every 8h, rolls the registry) |

## Not in git (secrets / bootstrap)
Two objects are created out-of-band and are **not** committed:
- `secret/registry-tls` — the step-ca TLS cert + private key
- `configmap/netframe-root-ca` — the NetFRAME root CA (for `step` to trust the CA)

## Bootstrap (one time)
```sh
# 0. On Randy: backing dir for the local PV
ssh randy 'mkdir -p /datastore/k8s-local/registry'

# 1. Issue the cert from step-ca (run on pve2, where step-ca lives).
#    Needs the JWK provisioner password (Vaultwarden). 'ca.netframe.local' must
#    resolve to pve2 (Pi-hole record, or a temporary /etc/hosts entry).
step ca certificate registry.netframe.local /tmp/registry.crt /tmp/registry.key \
  --provisioner 'admin@netframe.local' \
  --san registry.netframe.local --san 192.168.10.72 \
  --ca-url https://ca.netframe.local --root /etc/step-ca/certs/root_ca.crt
#    NOTE: CA default max TLS duration is 24h -> the CronJob keeps it fresh.

# 2. Create the TLS secret + root-CA configmap (kubeconfig = ~/.kube/config-rke2)
kubectl -n registry create secret tls registry-tls \
  --cert=/tmp/registry.crt --key=/tmp/registry.key
kubectl -n registry create configmap netframe-root-ca \
  --from-file=root.crt=/etc/step-ca/certs/root_ca.crt
shred -u /tmp/registry.key   # don't leave the key lying around

# 3. Apply the manifests
kubectl apply -f 10-storage.yaml -f 20-registry.yaml -f 30-cert-renew.yaml
```

## Auto-renewal
`30-cert-renew.yaml` runs a CronJob every 8h that:
1. `step ca renew` the current cert (mTLS auth with the existing cert — **no password**),
2. updates `secret/registry-tls`,
3. `rollout restart deploy/registry` (registry:2 loads its cert only at startup, so
   each renewal causes a brief restart blip — ~seconds, single RWO PV -> `Recreate`).

Force a run / check logs:
```sh
kubectl -n registry create job --from=cronjob/registry-cert-renew renew-now
kubectl -n registry logs job/renew-now -c renew    # OLD/NEW cert validity
```
## Recovery from an EXPIRED certificate
`step ca renew` authenticates with the current cert, so once that cert has
expired step-ca answers **HTTP 401** (`authority.authorizeRenew: certificate
expired on ...`) and no amount of retrying escapes it. The renewal CronJob is
then permanently stuck until a certificate is re-issued out of band.

Do **not** re-run bootstrap step 1-2 for this. That path issues the private key
on pve2 and then moves it to the operator workstation to create the Secret.
Use the bounded procedure instead:

```sh
bash reissue-expired-cert.sh      # + 40-cert-reissue.yaml
```

It differs from the bootstrap in exactly the ways that matter for key handling:
- the **private key is generated inside the cluster** by `40-cert-reissue.yaml`
  and only ever lands in `secret/registry-tls`; it never touches pve2 or the
  operator workstation
- only the **CSR (out)** and the **signed chain (in)** cross the pod boundary,
  and both are public material
- signing runs on pve2 via `step ca sign --provisioner-password-file`, so the
  provisioner password is referenced by path and **never read, printed, or
  transmitted**, and the one-time token `step` mints internally never reaches
  argv, a Kubernetes Secret, a log, or the workstation
- the signed chain is checked against the CSR's public key and the root CA
  **before** it is injected, so a mismatch fails without mutating anything

The script ends with the acceptance checks: Secret contents, the certificate
actually served on `.72:443`, and a `--cacert` trust-validating client that must
report `ssl_verify_result=0`.

Once a valid leaf is installed the normal `registry-cert-renew` CronJob resumes
on its own; nothing needs to be re-enabled.

Proven in anger 2026-09-05 (see the runbook's incident note).

## Access
- URL: `https://registry.netframe.local` (MetalLB `192.168.10.72`), Pi-hole DNS on `.177`/`.178`.
- Any client that trusts the NetFRAME root CA can push/pull today, e.g.:
  `skopeo copy --dest-tls-verify=true docker://busybox:1.36 docker://registry.netframe.local/busybox:1.36`
- **In-cluster pulls — DONE.** Every RKE2 node trusts the registry, so cluster **pods**
  can pull `registry.netframe.local/...`. On each node:
  ```sh
  # root CA
  install -d -m0755 /etc/rancher/rke2/tls
  cp netframe-root-ca.crt /etc/rancher/rke2/tls/netframe-root-ca.crt   # from `step ca root`
  # registries.yaml
  cat > /etc/rancher/rke2/registries.yaml <<'EOF'
  configs:
    "registry.netframe.local":
      tls:
        ca_file: /etc/rancher/rke2/tls/netframe-root-ca.crt
  EOF
  systemctl restart rke2-server   # or rke2-agent on Randy
  ```
  Do it **rolling, one node at a time, waiting for `Ready`** (preserves etcd quorum).
  RKE2/containerd 2.x renders this to `.../containerd/certs.d/registry.netframe.local/hosts.toml`.
  Verify: a pod with `image: registry.netframe.local/busybox:1.36` + `imagePullPolicy: Always` goes Running.

## Rollback
```sh
kubectl delete ns registry            # removes workload, PVC binding, cronjob
kubectl delete pv registry-randy-local
# data remains on Randy at /datastore/k8s-local/registry (reclaimPolicy: Retain)
```
