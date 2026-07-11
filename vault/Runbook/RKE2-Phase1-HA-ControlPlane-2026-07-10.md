# RKE2 Phase 1 — HA Control Plane (2026-07-10)

**Tags:** #runbook #rke2 #kubernetes #k8s
**Related:** [[Infrastructure/Proxmox Cluster]] · [[Runbook/Production-Readiness-Checklist-2026-07-10]] · `scripts/slurm/README.md` (GPU/RKE2 sequencing)

Stood up a **3-node HA control plane**. CPU-only (GPU scheduling deferred — see §GPU). Zero impact to existing infra.

## What's running
| Piece | Value |
|---|---|
| Nodes | `rke2-cp1` .51 (pve3/VMID 201), `rke2-cp2` .52 (pve4/202), `rke2-cp3` .53 (pve5/203) |
| VM spec | Debian 12 cloud-init, 2 vCPU / 4 GB / 40 GB local-lvm, VLAN 1 (vmbr0), `onboot=1`, ciuser `rke2` (Ares key) |
| Worker | `randy` .187 — **bare-metal agent on the PVE storage host** (not a VM); 2× E5-2690 v3 (48t) / 125 GiB; tainted `node.netframe.io/role=storage:NoSchedule`; kubelet-reserved → Allocatable **40 CPU / ~95.8 GiB** (added Phase 5, 2026-07-11 — see §Phase 5) |
| RKE2 | v1.35.6+rke2r1; **3 etcd members** (survives 1 node/host loss) |
| CNI | Cilium (`cni: cilium` in config) |
| **API VIP** | **`192.168.10.54:6443`** via kube-vip DaemonSet (ARP, leader-elected across CP nodes) |
| Service LB | MetalLB, pool `192.168.10.71-.75` (L2Advertisement) — verified |
| kubectl | Ares: `export KUBECONFIG=~/.kube/config-rke2` (→ VIP `.54`); kubectl in `~/.local/bin` |

## Build method (reproducible)
1. **VMs:** Debian 12 genericcloud qcow2 → `qm create`/`importdisk` + cloud-init (`--ipconfig0`, `--sshkeys`, `--ciuser rke2`). Script: scratchpad `mkvm.sh`.
2. **RKE2:** `/etc/rancher/rke2/config.yaml` with `token`, `cni: cilium`, `node-ip`, `tls-san` (all 3 IPs + `.54` + `rke2.netframe.local`); joins add `server: https://192.168.10.51:9345`. `curl -sfL https://get.rke2.io | sh -` + `systemctl enable --now rke2-server`.
3. **kube-vip:** RBAC + DaemonSet (`cp_enable`, `address: .54`, `vip_interface: eth0`, ARP, leader election).
4. **MetalLB:** `metallb-native.yaml` + IPAddressPool `.71-.75` + L2Advertisement.
- Join token persists on cp1: `/var/lib/rancher/rke2/server/node-token`.

## Guardrails honored
- New VMs only — GPUs, SLURM (QuarkyLab), Ollama (Jarvis), pve2/OPNsense all **untouched**.
- CP VMs on pve3/pve4/pve5 (not pve2). VLAN 1 (no bridge-VLAN changes needed).

## GPU (deferred — Phase 4)
Per `scripts/slurm/README.md`: don't run RKE2 GPU scheduling on a card SLURM/Ollama actively owns (both claim exclusive → silent job loss). QuarkyLab's 1× RTX 8000 = SLURM; Jarvis's 2× RTX 6000 = Ollama (72B tensor-split). **No free card today** → NVIDIA GPU Operator waits until a card is freed. When it goes in, retire the standalone nvidia-smi collector for the Operator's DCGM DaemonSet.

## Phase 2 — compute + storage (2026-07-10, DONE)
**Compute (workers):** chose to **run workloads on the CP nodes** (RKE2 servers are schedulable — no taints) rather than dedicated workers on QuarkyLab/Jarvis. Rationale: worker VMs on the GPU servers cost CPU contention with SLURM/Ollama + SLURM over-subscription risk + blast-radius coupling — and the reason to use those nodes (GPU) is deferred. Verified: a 3-replica deploy spread across cp1/cp2/cp3. Add dedicated workers later when workloads grow (cap cores + CPU-pin + reserve in `slurm.conf` if on GPU nodes).

**Storage (Randy NFS → dynamic PVCs):**
- Randy: dataset `datastore/k8s` (`/datastore/k8s`, 22.9T, `chmod 777`), NFS-exported to `.51/.52/.53` (`rw,sync,no_subtree_check,no_root_squash`). nfsd already listened on VLAN-1 `.10.187`.
- Cluster: `nfs-subdir-external-provisioner` (helm, ns `nfs-provisioner`) → **default StorageClass `nfs-client`** (`nfs.server=192.168.10.187`, `nfs.path=/datastore/k8s`, `archiveOnDelete=true`).
- ⚠️ k8s nodes need **`nfs-common`** installed (minimal cloud image lacks `mount.nfs` → `exit status 32`). Done on all 3.
- **Verified:** PVC Bound + pod wrote `PERSISTED-OK`, read back from Randy's ZFS. helm `helm` in Ares `~/.local/bin`.

## Phase 3 — first workload (2026-07-10, DONE)
**Uptime Kuma** as the platform-validating pilot (self-contained status/uptime monitor; complements Prometheus with synthetic checks). ns `uptime-kuma`: Deployment (1 replica, `Recreate`, requests 100m/128Mi, limits 500m/512Mi, readiness probe) + 2Gi PVC (`nfs-client` → Randy ZFS) + Service `LoadBalancer` → MetalLB **`192.168.10.71`**. Exercised every layer end-to-end (Deployment/PVC/LB/self-heal), verified HTTP 302. First visit to `http://192.168.10.71` creates the admin account. Swap for a real workload anytime. (Note: SQLite-on-NFS is fine for single-replica.)

## Housekeeping / next
- ✅ Ares kubeconfig (**cluster-admin**, `~/.kube/config-rke2`, mode 600) copied to Vaultwarden (2026-07-10).
- ✅ Pi-hole local DNS (2026-07-10): `rke2.netframe.local → .54`, `status.netframe.local → .71` — added on primary `.177`, synced to `.178`; verified resolving on both.
- ⏳ First-visit admin setup on Uptime Kuma (`http://192.168.10.71`).
- **Phase 4:** GPU Operator when a card frees (see §GPU).

## Phase 5 — Randy bare-metal storage worker (2026-07-11, DONE)
First worker node: **Randy joined as a bare-metal RKE2 agent directly on the Proxmox storage host** (not a VM — deliberate, so kubelet sits alongside the host ZFS/PBS/NFS/Jellyfin it must reserve against). `v1.35.6+rke2r1`, matches CP. `randy` → **Ready** in 44 s. Node stays schedulable-but-tainted for storage-adjacent workloads.

**Install:** `curl -sfL https://get.rke2.io | INSTALL_RKE2_TYPE=agent INSTALL_RKE2_VERSION=v1.35.6+rke2r1 sh -` then `systemctl enable --now rke2-agent`.

**Config** `/etc/rancher/rke2/config.yaml` (root, **0600** — holds join token):
```yaml
server: https://192.168.10.54:9345      # supervisor port — NOT 6443 (see gotcha)
token: <cp node-token>                   # from cp1 /var/lib/rancher/rke2/server/node-token
node-name: randy
node-ip: 192.168.10.187                   # register on VLAN 1 (same L2 as CP/VIP/corosync)
node-label:
  - "node.netframe.io/role=storage"
node-taint:
  - "node.netframe.io/role=storage:NoSchedule"
kubelet-arg:
  - "system-reserved=cpu=6000m,memory=24Gi,ephemeral-storage=2Gi"
  - "kube-reserved=cpu=2000m,memory=4Gi,ephemeral-storage=2Gi"
  - "eviction-hard=memory.available<2Gi"
  - "enforce-node-allocatable=pods"
```

**Kubelet reservations — sized to measured hardware, not defaults.** Randy = **2× E5-2690 v3 (24c/48t, `nproc=48`)**, 125.8 GiB RAM, ZFS ARC hard-capped **12.57 GiB** (`zfs_arc_max`), PBS jobs 02:00/03:00 + GC 03:00 + verify Sun 04:00, 16 nfsd threads, Jellyfin (idle, budgeted for transcode). `system-reserved` (6 CPU / 24 Gi) covers peak concurrent ZFS-scrub + PBS + NFS + transcode; `kube-reserved` (2 CPU / 4 Gi) for kubelet+containerd+Cilium. **Result: Allocatable = 40 CPU / ~95.8 GiB** (verified). When the +64 GB → 192 GB RAM lands, Allocatable mem just grows ~64 Gi; reservations unchanged unless `zfs_arc_max` is raised.
- **Not hard caps:** `enforce-node-allocatable=pods` (default) → reservations are *scheduling guardrails* that shrink Allocatable so the scheduler leaves host headroom; they do **not** cgroup-throttle ZFS/PBS/NFS (host services still burst freely into idle capacity). Enforcing `system-reserved` cgroups was deliberately avoided — it could throttle a PBS backup or ZFS scrub.

**Taint** `node.netframe.io/role=storage:NoSchedule` keeps general workloads off the storage backbone; infra DaemonSets (Cilium, kube-proxy, ingress-nginx, MetalLB speaker) tolerate it and run. Applied live via `kubectl taint` (kubelet only honors `node-taint` at *first* registration, so an already-joined node needs `kubectl taint`; config keeps it for future re-registration).

**⚠️ Gotchas hit:**
- **Agents register on the supervisor port `:9345`, NOT the apiserver `:6443`.** Pointing `server:` at `:6443` throws `Failed to validate connection … failed to get CA certs: Unauthorized` (apiserver rejecting the RKE2 bootstrap token). Verify: `curl -sk https://192.168.10.54:9345/cacerts` → 200.
- **Self-set `node-role.kubernetes.io/*` labels are blocked** by the NodeRestriction admission controller → used custom prefix `node.netframe.io/role=storage`.

**Post-join health (Cilium on a live PVE cluster member — verified intact):** corosync quorum **7/7 Quorate**, `datastore`+`bulk` **ONLINE**, nfs-server active (5 exports), PBS proxy+api active, egress still `via 192.168.30.1 dev vmbr0.30` (VLAN 30 untouched), VLAN 1 `.187` present.

**Rollback:** `/usr/local/bin/rke2-agent-uninstall.sh` on Randy — removes agent, containerd, and CNI cleanly.

**Guardrails honored:** PBS/ZFS/Jellyfin never restarted or reconfigured; pve2/OPNsense untouched; VLAN 30 storage path unchanged.
