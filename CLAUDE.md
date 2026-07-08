# NetFRAME Home Lab — Claude Code Context

## Who I Am
- Kyle Mason, USMC veteran, aviation professional transitioning to network engineering
- Pursuing CCNA via VetTec 2.0, MIS degree at Cleveland State University
- GitHub: machismo0311 | Site: kylemason.org
- Primary workstation: Ares (Debian 12, user: machismo, 192.168.10.199)
- Editor preference: nano
- Style: open-source tooling, step-by-step CLI, code blocks with separate explanation blocks

## Cluster Overview

**km-cluster** — 7-node Proxmox VE 9.2.3 (upgraded 2026-06-22)

### Proxmox Nodes
| Node | Hardware | IP | RAM | PVE | Kernel | Role |
|---|---|---|---|---|---|---|
| pve2 | HP EliteDesk 800 G4 (i7-8700) | 192.168.10.204 | 32GB | 9.2.3 | 7.0.12-1 | OPNsense host |
| pve3 | HP EliteDesk 800 G4 (i7-8700) | 192.168.10.201 | 48GB | 9.2.3 | 7.0.12-1 | Cluster node |
| pve4 | HP EliteDesk 800 G3 Mini (i5-7500T) | 192.168.10.202 | 32GB | 9.2.3 | 7.0.12-1 | Cluster node |
| pve5 | HP EliteDesk 800 G3 Mini (i5-7500T) | 192.168.10.203 | 32GB | 9.2.3 | 7.0.12-1 | Cluster node |
| sandbox | HP EliteDesk G4 (spare) | 192.168.70.x | — | — | — | Standalone lab — NOT in cluster |

### R730 Compute Nodes
| Node | Service Tag | IP | CPUs | RAM | GPU | PVE | Role |
|---|---|---|---|---|---|---|---|
| QuarkyLab | 1S8WR22 | 192.168.10.179 | 2x E5-2699 v4 | 512GB LRDIMM | RTX 8000 48GB† | 9.2.3 | Fernanda ML / DUNE agent |
| Jarvis | DWG7HH2 | 192.168.10.31 | 2x E5-2687W v4 | 384GB LRDIMM | 2× RTX 6000 24GB (48GB total)† | 9.2.3 | LLM inference |

†GPU plan (2026-06-30): **QuarkyLab → RTX 8000 48GB — INSTALLED & VERIFIED 2026-07-01** (nvidia-smi reports 46080 MiB on driver 550.163.01, kernel 6.14.11-9-pve; driver-free Turing TU102 swap). **Jarvis → 2× RTX 6000, 24GB each / 48GB total — INSTALLED & VERIFIED 2026-07-04** (nvidia-smi 24576 MiB ×2, driver 550.163.01, kernel 6.14.11-9-pve; PCI 03:00.0+82:00.0). Required a nouveau blacklist on first boot (nouveau grabbed the cards since the driver was staged pre-install). Ollama v0.31.1 GPU-backed, qwen2.5:72b pulled (tensor-splits across both). Fans managed by the `gpu-fan-control` daemon (see fan note below).
QuarkyLab: SSH works — `ssh quarkylab` via `fernanda@quarkylab` key (id_ed25519 on Ares). Kernel pinned to 6.14.11-9-pve via GRUB_DEFAULT. NVIDIA 550.163.01 verified working. RTX 8000 installed 2026-07-01 — driver-free swap (same 550.163.01 / 6.14.11 stack), nvidia-smi reports 48GB.
**VLAN 30 (2026-07-02):** QuarkyLab `192.168.30.179` and Jarvis `192.168.30.31` are dual-homed on the servers VLAN (mgmt/corosync stay on VLAN 1 `.10.x`).

### Randy (SuperMicro — Storage / PBS)
| Field | Value |
|---|---|
| Chassis | SuperMicro CSE-219U 2U 24-bay / X10DRU-i+ |
| IP (mgmt VLAN 1) | 192.168.10.187 |
| Service IP (VLAN 30) | 192.168.30.187 — NFS export + PBS + egress (dual-homed 2026-07-02) |
| IPMI | 192.168.20.22 (ADMIN, **VLAN 20** since 2026-07-03) |
| CPUs | 2x E5-2690 v4 (28 cores / 56 threads) |
| RAM | 128GB ECC DDR4 |
| Kernel | 7.0.12-1-pve |
| NIC | Mellanox ConnectX-3 MCX312A dual-port 10GbE |
| 10G link | nic3 → EX3400 xe-0/2/0 |
| Headscale IP | 100.64.0.2 |
| Boot | RAID-1 mirror, 2x Seagate ST200FM0053 185.8GB SAS via AVAGO 3108 MegaRAID |
| Data drives | 18x Toshiba AL15SEB18EQ 1.636TB 10K SAS + 4x Seagate ST2000NX0423 1.819TB SATA |
| ZFS layout | `datastore` = 4x RAIDZ2 — 3x 6-wide Toshiba + 1x 4-wide Seagate (36.7T raw / ~23T usable). All drives in-pool; no unallocated spares |
| GPU | RX 580 8GB (ROCm, display/transcoding only) |
| Proxmox UI | https://192.168.10.187:8006 |
| PBS UI | https://192.168.10.187:8007 (v4.2.2) |
| PBS fingerprint | `da:61:6a:4c:49:e8:87:03:08:1d:d7:31:ab:23:58:20:47:58:e8:77:4a:52:3d:39:0c:19:52:e0:67:ee:d9:c9` |

Randy in km-cluster. StorCLI at `/usr/sbin/storcli64`. JBOD mode enabled on AVAGO 3108.

## Networking
| Device | IP | Role |
|---|---|---|
| EX3400-48P | 192.168.10.50 | Core switch, JunOS 23.4R2-S7.4 |
| OPNsense | 192.168.10.1 (VM 100, pve2) | Router/firewall/DHCP, v25.7 |
| Headscale | 192.168.10.186 (LXC 105, pve3) | VPN, v0.29.1 — Ares (.1), Randy (.2), pve5 (.3), pve4 (.4), pve3 (.5), Jarvis (.6) |
| Pi-hole | 192.168.10.177 (pve1 LXC 103) | DNS — on Mac Mini standalone node, NOT pve3 |
| APC AP7901 PDU | EX3400 ge-0/0/38 | Managed PDU |
| Ares | 192.168.10.199 | Admin workstation |
| QuarkyLab iDRAC | 192.168.20.20 | **VLAN 20** (2026-07-03); pw rotated → Vaultwarden |
| Jarvis iDRAC | 192.168.20.21 | **VLAN 20** (2026-07-03); pw rotated → Vaultwarden |
| Randy IPMI | 192.168.20.22 | **VLAN 20** (2026-07-03); pw rotated → Vaultwarden |

### VLANs (EX3400)
| VLAN | ID | Subnet |
|---|---|---|
| Management | 1 | 192.168.10.0/24 |
| Trusted/iDRAC | 20 | 192.168.20.0/24 |
| Servers | 30 | 192.168.30.0/24 |
| IoT | 40 | 192.168.40.0/24 |
| VoIP | 50 | 192.168.50.0/24 |
| Guest | 60 | 192.168.60.0/24 |
| Lab | 70 | 192.168.70.0/24 |

> **Servers VLAN 30 populated 2026-07-02:** QuarkyLab `192.168.30.179`, Randy `192.168.30.187`, Jarvis `192.168.30.31` — **dual-homed** (corosync/mgmt/monitoring stay on VLAN 1; NFS/PBS/egress on VLAN 30). Node ports are now trunks (native 1 + tagged servers): QuarkyLab `ge-0/0/24`, Randy `xe-0/2/0`, Jarvis `ge-0/0/22`. **Update 2026-07-04: Jarvis VLAN 30 moved onto its new 10G ConnectX** — EX3400 **`xe-0/2/2`** set to access VLAN 30, Jarvis `vmbr1` (bridge on `enp132s0`) = `192.168.30.31`; mgmt/corosync stay on the onboard 1G (`ge-0/0/22` native VLAN 1). `ge-0/0/22`'s tagged VLAN 30 is now vestigial (harmless). See Runbook/VLAN30-Migration-Report-2026-07-02.md + Node-VLAN-Migration-Template.md.

### Power
| UPS | Feeds | Capacity |
|---|---|---|
| Middle Atlantic UPS-OL2200R | R730s, Randy, DS4246 | 6x 12V 9Ah AGM (76.4V) |
| Tripp Lite SMART1500VA | EX3400, UniFi, small compute | 1500VA |

## Key Services
| Service | Location | URL/Port | Notes |
|---|---|---|---|
| Proxmox Backup Server | Randy | https://192.168.10.187:8007 | v4.2.2, ZFS 36.7T (~23T usable, 19.5G used) — LXCs 02:00 daily, VMs 03:00 daily, 7d+4w retention |
| OPNsense | VM 100, pve2 | 192.168.10.1 | v25.7, onboot=1 |
| Headscale | LXC 105, pve3 | 192.168.10.186 | v0.29.1, onboot=1 |
| Pi-hole | pve1 LXC 103 | 192.168.10.177 | DNS — Mac Mini standalone, NOT pve3 |
| Homepage | pve3 LXC 106 (.148) | https://homepage.kylemason.org | Live widgets (Proxmox/Pi-hole/Jellyfin/Scrutiny/UPS); Power & UPS group via PeaNUT container (:8081→8080, NUT bridge); NPM proxy host id 4 + Lets Encrypt (CF DNS-01) + basic auth (kyle); :3000 firewalled to NPM; tokens/creds in /opt/homepage/config + compose (not git). See Homepage-Setup-2026-06-26.md & Power Distribution.md |
| Open WebUI | LXC 107, pve3 (.185) | http://chat.netframe.local | Chat UI (ChatGPT-style) → llm_router `:8000` via OpenAI endpoint; models `local`/`rag`. Native pip (Debian 12 CT, /opt/open-webui venv, systemd), NPM proxy host id 6, Pi-hole DNS →.181, onboot=1. Created 2026-07-05. First visit creates the admin account. **TODO: add CT 107 to PBS backup** |
| nginx-proxy (NPM) | LXC 101, pve3 (.181) | Admin http://192.168.10.181:81 | onboot=1; :81 restricted to Ares (.199) via DOCKER-USER fw (F-05) ✅ |
| Vaultwarden | LXC 102, pve3 | http://192.168.10.182 | Docker Compose, healthy ✅ onboot=1 |
| Prometheus/Grafana/Loki | LXC 103, pve3 (.183) | Grafana http://192.168.10.183:3000 | Stack active ✅; 8 nodes scraped; Prom/Loki localhost-only (F-03) |
| Scrutiny (drive health) | LXC 103, pve3 + collectors on Randy, QuarkyLab & Jarvis | http://192.168.10.183:8080 | ~50 drives monitored; InfluxDB backend; binary collector via systemd timer every 6h on Randy (43), QuarkyLab (7) and Jarvis (1, added 2026-07-02); collector.yaml `host.id` + endpoint `192.168.10.183:8080` |
| Wazuh | QuarkyLab VM 104 | `https://192.168.10.184` | SIEM — migrated from pve2 |
| step-ca | pve2 | https://192.168.10.204:443 | *.netframe.local TLS — active ✅ password at /etc/step-ca/secrets/password |
| Jellyfin | Randy (host) | http://192.168.10.187:8096 | v10.11.11; media at /datastore/media/{movies,tv,music}; GPU transcoding pending RX 580 power cable |
| Ollama | Jarvis | llm.netframe.local | v0.31.1, **GPU-backed** (2× RTX 6000); models on `tank/models` ZFS dataset (7.2T pool) since 2026-07-08 (was /opt/models 98G LV, now reclaimed) |

**Wazuh VM 104 is on QuarkyLab** (migrated from pve2). IP: 192.168.10.184 (DHCP). Dashboard: `https://192.168.10.184`.

## Storage
- **Randy ZFS:** `datastore` — 4x RAIDZ2 (3x 6-wide Toshiba 1.636TB 10K SAS + 1x 4-wide Seagate ST2000NX0423 1.819TB SATA), 36.7T raw / ~23T usable, 19.5G used
- **Randy boot:** RAID-1, 2x Seagate ST200FM0053 via AVAGO 3108 MegaRAID
- **Jarvis root:** pve LVM 56GB — sda (186GB ST200FM0053 SAS SSD) added to VG 2026-06-22 after disk-full during upgrade; boot also on internal IDSDM SD (`sdb`). (The old `/opt/models` 98G LV was reclaimed 2026-07-08 after the ZFS move below — VG VFree now ~136G)
- **Jarvis ZFS (2026-07-08):** new drives on the onboard **LSI SAS-3 3008 (HBA330, IT mode)**, by-id. `tank` = raidz1 5× 2TB HDD (ST2000NX046x), **7.2T** usable, `/tank` — model library + bulk; `scratch` = 1× 200GB SSD (ST200FM0053 `sdc`), 181G, `/scratch` — fast scratch. Ollama `OLLAMA_MODELS` moved LV→**`tank/models`** (drop-in `ollama.service.d/override.conf`; old 98G `/opt/models` LV reclaimed same day post-verify). Bay-0 SSD is the OS disk → only the 2nd SSD was free, so `scratch` is single-disk.
- **DS4246 JBOD:** 13x Toshiba 1.8TB + 19x Dell/Seagate 2TB SAS, via LSI 9207-8e (IT mode) — passthrough pending

## Active Projects

### llm_router.py (Jarvis)
FastAPI, OpenAI-compatible. Routes between local Ollama (Qwen2.5 72B, Jarvis 2× RTX 6000, 48GB total) and Claude API fallback (`claude-opus-4-8`, adaptive thinking, official SDK). **ACTIVE 2026-07-04** — systemd `llm_router.service` on Jarvis `:8000`, source in `Home-Lab/scripts/llm_router/`. Escalates to Claude on `escalate:true` / `model=claude-*` / local failure. Claude fallback gated on `ANTHROPIC_API_KEY` in `/etc/llm_router.env` (unset → local-only). Fronted by **NPM `http://llm.netframe.local`** (proxy host id 5 → .31:8000, HTTP-only) + Pi-hole local DNS `llm.netframe.local→.181` (resolves only for Pi-hole clients). **RAG (2026-07-05):** `model:"rag"` grounds answers on the Home-Lab vault (nomic-embed-text via Ollama + numpy cosine index, 418 chunks, `rag_ingest.py` to rebuild) with `[source]` citations. Local context capped `OLLAMA_NUM_CTX=8192` (72B Q4 ~47GB barely fits 48GB → minor CPU spill; 4096 = fully-GPU). Note: Ollama has no logprobs, so routing is by flag/model/failure, not confidence; streaming not yet implemented.

### DUNE Agent — Fernanda (QuarkyLab)
RAG pipeline over DUNE experiment codebase. RTX 8000 48GB (installed 2026-07-01). Vector store: ChromaDB or Qdrant (TBD).

### NetFRAME Dashboard
Cyberpunk React wall dashboard (v3, netframe-dashboard-v3.jsx) on Dell P2722H.

## Coding Conventions
- All scripts use bash unless Python is explicitly required
- Python scripts use venv, requirements.txt
- Systemd unit files for all persistent services
- No Docker unless explicitly requested (prefer LXC on Proxmox)
- Secrets go in Vaultwarden, never hardcoded
- Label convention: [DEVICE]-[PORT], TIA-606 cable colors

## Important Safety Notes
- ALWAYS check prior conversation before touching pve2 network config (June 15 outage)
- QuarkyLab kernel MUST stay on 6.14.11-9-pve — GRUB_DEFAULT is pinned; 6.17+ breaks NVIDIA 550; never run kernel upgrades or change GRUB default on QuarkyLab
- Jarvis is ALSO now pinned to 6.14.11-9-pve (GRUB_DEFAULT; NOT proxmox-boot-tool) for its NVIDIA 550.163.01 GPU stack — do not change GRUB default or upgrade the kernel on Jarvis either
- R730 GPU fan control (QuarkyLab & Jarvis): iDRAC has **no GPU-temp visibility**, so natively it offers only the loud fixed third-party ramp or a quiet baseline that won't ramp for GPU heat. **Measured 2026-07-04:** with `ThirdPartyPCIFanResponse=Enabled` (Jarvis's default on install) the RTX cards forced **~14,800 RPM at idle** (jet engine); disabling it drops to ~4,080 RPM but then fans do **not** ramp for GPU load (single compute-bound card = 81 °C fans-flat; real 72B dual-GPU load = only 63 °C — bandwidth-bound, so the small-model single-card case is worst). **QuarkyLab** already has it Disabled (why it's quiet); toggling it there does nothing at runtime since it was never loud. **Jarvis runs the `gpu-fan-control` daemon** (source in `Home-Lab/scripts/`, installed `/usr/local/sbin/gpu-fan-control.sh` + systemd unit) — a closed-loop nvidia-smi→`ipmitool` manual fan curve (15% idle → up to 100%) with **failsafe-to-auto** on any crash/stop, self-asserting third-party=Disabled at startup. Bare manual `ipmitool raw 0x30 0x30` is only safe inside that failsafed daemon. NOTE: iDRAC SCP queue was stuck (LC068, pending BIOS job) so the setting is asserted in-band, not persisted as an iDRAC attribute. Full detail: Compute/Dell R730 - General Node.md (Fan/Thermal) + ML Node (investigation).
- QuarkyLab SSH: `ssh quarkylab` (IP 192.168.10.179) via fernanda@quarkylab key (id_ed25519 on Ares)
- QuarkyLab iDRAC BIOS `ErrPrompt` = **Disabled** (2026-07-02): a tripped chassis-intrusion switch (lid opened) no longer halts POST at the F1 "Cover was previously removed" prompt — that prompt renders on the onboard Matrox VGA, NOT the GPU, so a monitor on the RTX card looks dead. To change BIOS attrs on these iDRAC 8 boxes: racadm isn't installed and Ares curl can't do the iDRAC's old TLS — run Redfish curl FROM the node (PATCH Bios/Settings + POST a config job; applies on reboot). See Compute/Dell R730 - ML Node.md
- Wazuh VM 104 (QuarkyLab, .184) has NO qemu-guest-agent → a QuarkyLab host reboot hard-stops it (unclean) and `wazuh-indexer` comes back unhealthy (dashboard 503). Fix after any QuarkyLab reboot: `qm stop 104 && qm start 104`, wait ~4 min; healthy = dashboard root returns 302→/app/login (NOT 200), manager `:55000`=401, indexer `:9200`=000/refused from LAN is normal. Permanent fix: install qemu-guest-agent in the VM + `qm set 104 --agent enabled=1` + one cold start. onboot=1 is set.
- Tailscale overwrites /etc/resolv.conf on ALL nodes — run `tailscale set --accept-dns=false` and set nameserver to 192.168.10.177 before any apt operations
- Headscale Phase 2 pending: QuarkyLab + Fernanda's Mac (ferpsihas@, fus22-009897) must migrate together — do not migrate one without the other
- QuarkyLab/Randy/Jarvis migrated to Servers VLAN 30 (2026-07-02, **dual-homed**): corosync + management + monitoring stay on VLAN 1 (`.10.179/.187/.31`); NFS `/data`, PBS backup, and internet egress ride VLAN 30 (`.30.179/.187/.31`, default gw `.30.1`). Corosync deliberately NOT moved (keep the ring on stable L2). EX3400 node ports are trunks (native 1 + tagged servers): QuarkyLab ge-0/0/24, Randy xe-0/2/0, Jarvis ge-0/0/22. Rollback anchors on each node (`interfaces.bak-vlan30-*` etc.). See Runbook/VLAN30-Migration-Report-2026-07-02.md + Node-VLAN-Migration-Template.md. NOTE: `/data` mount and `pbs-workspace-backup.sh` PBS_REPOSITORY point at `192.168.30.187` (only reachable from the VLAN-30 GPU nodes). **⚠️ PBS storage.cfg was ALSO repointed to `.30.187` by this migration, which SILENTLY BROKE all pve-node (VLAN-1) backups from 2026-07-02 — bulk PBS uploads from pve3 route to `.30.187` via a bogus gateway `192.168.1.1` and stall at 0 B. FIXED 2026-07-06: `randy-pbs` storage repointed to Randy's dual-homed VLAN 1 IP `192.168.10.187` (reachable directly on vmbr0 by every node). Nightly LXC job now covers 101/102/103/105/106/107; keep PBS storage on `.10.187`. **10G path (2026-07-08):** added `randy-pbs-10g` storage → `.30.187` (same datastore/fingerprint) restricted to `nodes QuarkyLab,Jarvis,Randy` (they reach .30.187 direct on vmbr0.30 @10G); VM 104 (Wazuh, QuarkyLab) split into its own job on `randy-pbs-10g` for 10G backups; VM 100 + all LXCs stay on `randy-pbs` (.10.187). See Runbook/Jarvis-LLM-Platform-2026-07-05.md §9.**
- VLAN activation COMPLETE (2026-06-25): EX3400 ge-0/0/46 trunk live to UniFi Port 24, verified end-to-end. KEY: native-vlan-id goes at INTERFACE level on this EX3400 (ELS), NOT under unit 0 family ethernet-switching. pve2 vmbr2/nic2 auto-start DISABLED (unused bridge with live UniFi cable caused trunk loop) — do not re-enable without removing its cable. See VLAN-Activation-2026-06-25.md
- Ares mgmt path: the **wired** leg `enp0s31f6` (192.168.10.100) is primary — keep it connected during any pve2/OPNsense maintenance. **Correction (2026-07-03):** Ares WiFi `wlp2s0` was found on **VLAN 1 LAN (192.168.10.199)**, not the WAN side as previously noted — so WiFi *can* currently reach mgmt, but the wired leg flapped/was link-down at session start; treat wired as authoritative and verify `ip route get 192.168.20.x` egresses `enp0s31f6.20` before trusting VLAN 20 tests (a down wired leg silently reroutes VLAN 20 via WiFi→OPNsense). Ares also carries a VLAN 20 leg `enp0s31f6.20` (192.168.20.199) as the OOB/BMC jump host.
- **OOB/BMC on VLAN 20 (2026-07-03, Phase 1 security segmentation):** all three BMCs moved off flat VLAN 1 — QuarkyLab iDRAC `192.168.20.20`, Jarvis iDRAC `192.168.20.21`, Randy IPMI `192.168.20.22` (802.1q VLAN 20 tagged; default creds root/calvin + ADMIN **rotated → Vaultwarden**). EX3400 ports ge-0/0/30·32·44 are tagged-VLAN-20-only; reach BMCs from Ares' `enp0s31f6.20`. Randy IPMI = channel 1; **enabling VLAN zeroes the IP** — re-apply `ipmitool lan set 1 ipaddr` after `lan set 1 vlan id`. Still pending: OPNsense firewall to deny non-Ares→VLAN 20 + no BMC egress (Phase 1.5). See Runbook/Security-VLAN-Segmentation-Phased-2026-07-03.md
- ifreload -a does NOT apply bridge-vlan-aware on pve2 — requires full reboot of pve2
- Randy boot drives RAID-1 via AVAGO 3108 MegaRAID — do not reconfigure
- Randy data drives use separate LSI 9207-8e HBA in IT mode — two different cards
- Randy JBOD mode may reset after reboot — re-run `storcli64 /c0 set jbod=on && storcli64 /c0/eall/sall set jbod`
- Randy AVAGO 3108 relocated to a known-good PCIe slot 2026-07-01 after its original slot failed (controller undetected at POST → "no boot device"). Original slot is DEAD — do not reuse. Triage: no MegaRAID banner at POST = physical/slot fault, NOT a BIOS/OpROM setting; blinking-green D13 LED = card healthy. See Runbook/Randy-PCIe-Slot-Recovery-2026-07-01.md
- Randy corosync singleton after reboot: from pve2 `pvecm delnode Randy`, then on Randy `pkill pmxcfs; systemctl start pve-cluster`
- Jarvis root was 6GB (disk-full during upgrade) — now 56GB with sda added to pve VG
- pve3 LXCs (101/102/103/105/106/107) all have onboot=1 set — verify before rebooting pve3 (107 = Open WebUI, added 2026-07-05)
- Proxmox 9.x ships enterprise repos in .list AND .sources formats — disable all 6 files
- Do not mix RDIMMs and LRDIMMs (confirmed incompatible on R730s)
- StorCLI not in apt — download from Broadcom portal manually, SCP to node
- Supermicro BIOS flash with FDT difference requires two-stage boot — let STARTUP.NSH auto-run
