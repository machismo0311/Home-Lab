# 🖥️ Dell R730 — quarkylab (General Node)
**Tags:** #compute #dell #r730
**Related:** [[Compute/Dell R730 - ML Node]] · [[Infrastructure/Proxmox Cluster]] · [[Power Distribution]]

---

## Status: ⏸️ Pending — BIOS update in progress

- iDRAC reachable at **192.168.10.20**
- iDRAC/LC needs update to 2.86 first (same TFTP procedure as Jarvis)
- BIOS update blocked by suspected **mismatched CPU steppings** (silent QPI hang)
- Not yet installed as a Proxmox cluster node

---

## Hardware Specs

| Component | Spec |
|---|---|
| Model | Dell PowerEdge R730 |
| Hostname (planned) | quarkylab |
| Service Tag | **1S8WR22** |
| Form Factor | 2U |
| Rack Position | U15–U16 |
| **CPU** | 2× Intel Xeon E5-2699 v4 (target) |
| CPU Cores | 44c / 88t total (when correct CPUs installed) |
| **RAM** | 512 GB ECC DDR4 (target) |
| Storage | TBD (see [[Infrastructure/Storage]]) |
| NICs | 4× 1G onboard |
| Remote Mgmt | iDRAC 8 |
| **iDRAC IP (current)** | **192.168.10.20** |
| Depth | ~28" — **rear panel removed** from NetFRAME CS9000 |

---

## Purpose (once online)

General-purpose compute in the Proxmox cluster:
- Wazuh SIEM (requires ≥4GB RAM — deploy as VM, not LXC)
- Jellyfin media server
- Vaultwarden overflow / redundancy
- General VM hosting
- Heavy workloads that don't need GPU

---

## iDRAC / Firmware Update Procedure

Same procedure as [[Compute/Dell R730 - ML Node]]:

```bash
# Step 1: Update iDRAC/LC to 2.86 via TFTP (no Enterprise license required)
racadm -r 192.168.10.20 -u root -p <pass> fwupdate -g -u -a <tftp-server-ip> -d firmimg.d7

# Step 2: After iDRAC reboots, flash BIOS via web UI
# https://192.168.10.20 → Maintenance → System Update

# Step 3: Verify POST
# If silent hang with no error → check CPU S-spec steppings match
```

> [!WARNING] CPU Stepping Issue
> Mismatched CPU S-spec steppings cause a **silent QPI hang** — no error displayed, system just hangs at POST. Verify both CPU S-spec codes match before seating. This is the current suspected root cause of POST failures.

See `Home-Lab/docs/r730-bios-recovery-runbook.md` for full recovery procedure.

---

## iDRAC Access

```bash
# Web UI
https://192.168.10.20

# CLI
racadm -r 192.168.10.20 -u root -p <pass> getsysinfo
racadm -r 192.168.10.20 -u root -p <pass> serveraction powerup
racadm -r 192.168.10.20 -u root -p <pass> getsel   # event log
```

---

## Proxmox Role (planned)

- Join existing pve1–pve5 cluster
- No GPU passthrough required
- Will host Wazuh SIEM as VM (minimum 4GB RAM for indexer)
- Storage: local + NFS from DS4246 once connected

---

## Related
- [[Compute/Dell R730 - ML Node]] — Jarvis (iDRAC: 192.168.10.21)
- [[Power Distribution]] — UPS B bus
- [[Infrastructure/Proxmox Cluster]] — Cluster join procedure
