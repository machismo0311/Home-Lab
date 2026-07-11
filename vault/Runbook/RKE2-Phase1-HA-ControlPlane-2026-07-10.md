# RKE2 Phase 1 — HA Control Plane (2026-07-10)

**Tags:** #runbook #rke2 #kubernetes #k8s
**Related:** [[Infrastructure/Proxmox Cluster]] · [[Runbook/Production-Readiness-Checklist-2026-07-10]] · `scripts/slurm/README.md` (GPU/RKE2 sequencing)

Stood up a **3-node HA control plane**. CPU-only (GPU scheduling deferred — see §GPU). Zero impact to existing infra.

## What's running
| Piece | Value |
|---|---|
| Nodes | `rke2-cp1` .51 (pve3/VMID 201), `rke2-cp2` .52 (pve4/202), `rke2-cp3` .53 (pve5/203) |
| VM spec | Debian 12 cloud-init, 2 vCPU / 4 GB / 40 GB local-lvm, VLAN 1 (vmbr0), `onboot=1`, ciuser `rke2` (Ares key) |
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
