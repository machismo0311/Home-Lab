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

## Housekeeping / next
- ⏳ Copy the Ares kubeconfig (**cluster-admin**) to Vaultwarden.
- ⏳ Add Pi-hole local DNS `rke2.netframe.local → 192.168.10.54` (already in cert SANs).
- **Phase 2:** CPU worker node(s) + Randy NFS storage class (`nfs-subdir` provisioner). *Note operational cost of placing workers on QuarkyLab/Jarvis — CPU contention with SLURM/Ollama; size/cap accordingly or run light workloads on the CP nodes / EliteDesks instead.*
- **Phase 3:** first CPU workload (orchestration-worthy only; house rule stays LXC-first).
