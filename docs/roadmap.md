# NetFRAME Delivery Record

What has shipped, and what is in progress. Preserved verbatim from the README.

Back to the [platform overview](../README.md).

---

## Planned / In Progress

- [x] Randy commissioned - PBS live, ZFS datastore 36.7TB raw / ~23TB usable
- [x] Cluster upgrade - all cluster nodes to PVE 9.2.3 / kernel 7.0.12-1 (2026-06-22); Randy kernel/ZFS-only, stays on pve-manager 9.1.1
- [x] QuarkyLab RTX 8000 48GB swap ✅ 2026-07-01 (nvidia-smi reports 48GB, NVIDIA 550.163.01)
- [x] Jarvis 2× RTX 6000 install ✅ 2026-07-04 (24GB each / 48GB total; Ollama GPU-backed, qwen2.5:72b)
- [x] Multi-tenant SLURM + Apptainer + MPS GPU sharing on QuarkyLab ✅ validated 2026-07-02 (research preemption + per-job VRAM caps)
- [x] Backup schedules configured - daily to randy-pbs, 7d+4w retention
- [x] Wazuh SIEM + Promtail→Loki on all 8 nodes ✅ 2026-06-25
- [x] DS4246 → Randy - pool `bulk` built 2026-07-08, 3rd vdev added 2026-07-17 (8+8+6-wide RAIDZ2, 80.0TB raw / ~55 TiB usable, reboot-verified)
- [x] VLAN activation ✅ 2026-06-25 - EX3400 ge-0/0/46 trunk live, verified end-to-end. Fix: native-vlan-id at interface level (ELS)
- [x] Scrutiny - drive health UI live (~56 drives, collectors on Randy + QuarkyLab, 6h) ✅
- [x] RKE2 Kubernetes ✅ Phases 1-7 (2026-07-10/11) - HA control plane (VMs 201-203, VIP .54), Cilium, MetalLB (.71-.75), Randy NFS StorageClass + bare-metal storage worker, private registry (step-ca TLS + auto-renew). **NVIDIA GPU Operator deferred** (SLURM/Ollama own the cards). See `vault/Runbook/RKE2-Phase1-HA-ControlPlane-2026-07-10.md`
- [x] Headscale Phase 1 - pve3/4/5/Jarvis migrated to self-hosted (2026-06-22)
- [ ] Large-scale DUNE dataset landing + offsite restic→B2 backup tier (parked pending data)
- [ ] Headscale Phase 2 - QuarkyLab + a DUNE researcher's Mac (must migrate together)
- [ ] FreePBX + 5× Cisco CP-8841 VoIP phones
- [x] Cyberpunk monitoring dashboard - live API integration

---
