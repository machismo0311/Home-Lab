# 🖥️ Dell R730 — Jarvis (General / LLM Node)
**Tags:** #compute #dell #r730 #llm
**Related:** [[Compute/Dell R730 - ML Node]] · [[Infrastructure/Proxmox Cluster]] · [[Power Distribution]]

---

## Status: 🟢 Online — km-cluster node (2× RTX 6000 installed & verified 2026-07-04)

- **Host IP (mgmt, VLAN 1):** 192.168.10.31 · **Service IP (VLAN 30):** 192.168.30.31 — dual-homed 2026-07-02 (see [[Runbook/VLAN30-Migration-Report-2026-07-02]])
- **iDRAC:** 192.168.20.21 (VLAN 20 since 2026-07-03; root pw in Vaultwarden — reach from Ares `enp0s31f6.20`)
- Member of km-cluster (PVE 9.2.3); Headscale 100.64.0.6
- **Scrutiny collector** installed 2026-07-02 (reports `sda` SMART to hub `192.168.10.183:8080`, 6h timer)
- Kernel pinned to **6.14.11-9-pve** (GRUB_DEFAULT; NOT proxmox-boot-tool) for the NVIDIA GPU stack — do not upgrade/change
- **2× RTX 6000 INSTALLED & VERIFIED 2026-07-04** — Quadro RTX 6000, **24 GB each / 48 GB total** (nvidia-smi 24576 MiB ×2, driver 550.163.01, kernel 6.14.11-9-pve); QuarkyLab's old RTX 6000 + a new one. Required a nouveau blacklist on first boot (see install section). Fans managed by the **`gpu-fan-control` daemon**.

> [!NOTE] iDRAC IP was originally static 10.10.198.38; changed via front panel to 192.168.10.21. iDRAC MAC 18:66:da:97:0f:8e.

---

## Hardware Specs

| Component | Spec |
|---|---|
| Model | Dell PowerEdge R730 |
| Hostname | Jarvis |
| Service Tag | DWG7HH2 |
| Form Factor | 2U |
| Rack Position | U18–U20 |
| **CPU** | 2× Intel Xeon E5-2687W v4 (12c each · 48t total) |
| **RAM** | 384 GB LRDIMM ECC DDR4 |
| **GPU** | 2× NVIDIA Quadro RTX 6000 **24 GB each (48 GB total)** — installed & verified 2026-07-04 (driver 550.163.01, `03:00.0`+`82:00.0`) |
| Storage | pve LVM 56GB — sda (186GB ST200FM0053 SAS SSD) added to VG 2026-06-22 after disk-full during upgrade; **/opt/models 98G LV** (2026-07-01) for LLM weights |
| NICs | 4× Broadcom BCM57800 1/10G onboard (nic0–3; nic2→vmbr0 = mgmt/corosync VLAN 1) + Mellanox ConnectX-3 10GbE (`enp132s0`→vmbr1 = **VLAN 30 servers** via EX3400 xe-0/2/2, 2026-07-04) |
| Remote Mgmt | iDRAC 8 (192.168.10.21) |
| Depth | ~28" — **rear panel removed** from NetFRAME CS9000 |

---

## Purpose

LLM inference node (**GPU software stack ready; awaiting cards**):
- **llm_router.py** — FastAPI, OpenAI-compatible; routes between local Ollama (Qwen2.5 72B on 2× RTX 6000) and Claude API fallback. **Inactive** until the GPUs are installed.
- Ollama v0.31.1 (`llm.netframe.local`) — installed, CPU-only for now; models on /opt/models (98G LV). Awaiting GPUs.
- General VM hosting / heavy non-GPU workloads.

> [!WARNING] Power
> Runs on **UPS A** (Middle Atlantic UPS-OL2200R, the bottom/ML bus, shared with QuarkyLab + Randy + DS4246). See [[Power Distribution]].

---

## iDRAC Access

```bash
https://192.168.10.21                                   # Web UI (root/calvin)
racadm -r 192.168.10.21 -u root -p calvin getsysinfo
racadm -r 192.168.10.21 -u root -p calvin serveraction powercycle
```

> Historical BIOS/iDRAC recovery (CPU stepping / firmware) for the R730s: see `Home-Lab/docs/r730-bios-recovery-runbook.md`.

---

## 2× RTX 6000 — INSTALLED & VERIFIED 2026-07-04

- **GPUs:** 2× Quadro RTX 6000, **24 GB each / 48 GB total** (nvidia-smi 24576 MiB ×2), driver 550.163.01, kernel 6.14.11-9-pve. PCI `03:00.0` + `82:00.0`, both `Kernel driver in use: nvidia`.
- **nouveau conflict (fixed):** on first boot with GPUs present, `nouveau` grabbed both cards (the driver was staged when no GPU was installed, so it was never blacklisted) → `nvidia-smi` failed "No devices probed." Fix: `/etc/modprobe.d/blacklist-nouveau.conf` (`blacklist nouveau` + `options nouveau modeset=0`) + `update-initramfs -u` + reboot → nvidia binds.
- **ConnectX-3 10GbE** added same trip: `84:00.0` → `enp132s0`. **Cabled + configured 2026-07-04 to carry VLAN 30** (NFS/PBS/egress): EX3400 **`xe-0/2/2`** set to access VLAN 30 (`servers`); Jarvis `vmbr1` (bridge on `enp132s0`) holds `192.168.30.31/24` gw `.30.1`; old tagged `vmbr0.30` on the 1G removed. Mgmt/corosync stay on the onboard 1G (`vmbr0`/nic2, VLAN 1). Verified: 10000Mb/s, default route + PBS `.30.187` over the 10G, cluster 7/7 quorate. (2nd port `enp132s0d1` down/unused.)
- **Ollama** now GPU-backed (v0.31.1, `/opt/models`); **qwen2.5:72b** pulled (~47 GB, tensor-splits across both cards). `llm_router.py` can be activated.
- Headscale Phase 2: QuarkyLab + Fernanda's Mac must migrate together — do not migrate one without the other.

---

## Fan / Thermal — as-built (GPU-aware daemon)

**The story (measured 2026-07-04):** on install, iDRAC's `ThirdPartyPCIFanResponse` was at its **default (Enabled)**, so the two unrecognized RTX cards triggered a **full-speed ramp (~14,800 RPM) at idle** (jet engine). Disabling it (matching QuarkyLab) drops fans to the ~4,080 RPM baseline — but with it disabled iDRAC has **no GPU-temp visibility**, so the fans do **not** ramp for GPU heat: a single compute-bound card hit **81 °C** at baseline with fans flat, while real 72B dual-GPU load only reached **63 °C** (tensor-parallel inference is bandwidth-bound, not compute-bound — the small-model single-card case is the worst case, not the big model).

**Solution deployed — `gpu-fan-control` daemon** (source: `Home-Lab/scripts/gpu-fan-control.{sh,service}`; installed at `/usr/local/sbin/gpu-fan-control.sh` + `/etc/systemd/system/gpu-fan-control.service`). Closed-loop service: reads max GPU temp via `nvidia-smi` every 5 s and sets fan % with iDRAC manual control (`ipmitool raw 0x30 0x30`):
- **Curve:** <50 °C → 15% (~4,080 RPM, quiet idle); 25/35/45/60/80/100% at 50/60/70/75/80/85 °C (2 °C down-hysteresis).
- **Chassis safety net:** exhaust ≥45 °C forces ≥70% (covers CPU-heavy load the GPU curve can't see).
- **Failsafe:** any stop/crash/`nvidia-smi` read-failure → hands fans back to iDRAC auto (`0x30 0x30 0x01 0x01`); with third-party disabled that's the measured-safe ~4,080 baseline. Both `ExecStopPost` and an in-script trap revert; `Restart=on-failure`; `enabled` at boot.
- **Self-contained:** re-asserts `ThirdPartyPCIFanResponse=Disabled` (`ipmitool raw 0x30 0xce …`) at every startup, so it survives reboots without depending on the iDRAC persistent attribute (which couldn't be set via SCP — see note).
- **Verified 2026-07-04:** fans ramped 15→35% tracking GPU 40→64 °C; killing the daemon mid-load reverted to auto with cards staying safe; clean `systemctl stop` → inactive.

> [!NOTE] The earlier blanket "never use `ipmitool raw 0x30 0x30`" rule applies to an **unmanaged** manual setting. A **failsafed** daemon that reverts to a *measured-safe* auto baseline on any failure is a different, acceptable risk profile — that is what makes this safe.

> [!WARNING] iDRAC SCP config queue was stuck (LC068 / a pending `ErrPrompt` BIOS job blocked import/export; Redfish `DELETE` job returned 400 on fw 2.86). That's why the fan-response setting is asserted in-band by the daemon rather than persisted as an iDRAC attribute. `ThirdPartyPCIFanResponse` byte mapping (via `ipmitool raw 0x30 0xce 0x01 …`): read `…05 00 01 00 00` = iDRAC **Disabled** (quiet); `…05 00 00 00 00` = **Enabled** (loud) — the ipmitool bit reads inverted vs the iDRAC label.

---

## Day-of-install commands (staged 2026-07-04)

### Pre-install baseline (captured while up, for post-install diff)
- Kernel `6.14.11-9-pve` ✅ · NVIDIA `550.163.01` DKMS installed ✅ · Ollama 0.31.1 active ✅ · `nvidia-smi` fails "no driver comms" (expected — no GPU yet).
- PCI (before): 4× Broadcom BCM57800 `01:00.0–.3` (onboard NDC = nic0–3; **nic2 UP = live mgmt link, do not disturb**), Matrox G200 VGA `09:00.0`. **No NVIDIA, no Mellanox.**
- After install expect **+2 NVIDIA TU102 (RTX 6000)** and **+1 Mellanox ConnectX** (new nicX).

### Pre-empt the F1 halt — `ErrPrompt=Disabled` (Jarvis iDRAC)
Run from Ares' VLAN 20 leg (`enp0s31f6.20`, carrier=1). The BMC stays powered with the host off, so this can run before or after power-down — it applies at the next (post-install) boot. Root pw in Vaultwarden.
```bash
IDRAC=192.168.20.21
B="https://$IDRAC/redfish/v1/Systems/System.Embedded.1/Bios"
C="curl -sk --ciphers DEFAULT@SECLEVEL=0 -u root:<vaultwarden-pw>"   # SECLEVEL=0 required for iDRAC-8 TLS
$C -X PATCH "$B/Settings" -H 'Content-Type: application/json' -d '{"Attributes":{"ErrPrompt":"Disabled"}}'
$C -X POST "https://$IDRAC/redfish/v1/Managers/iDRAC.Embedded.1/Jobs" -H 'Content-Type: application/json' -d "{\"TargetSettingsURI\":\"$B/Settings\"}"
# verify after boot:  $C "$B" | tr ',' '\n' | grep -i errprompt   → "ErrPrompt":"Disabled"
```

### Thermal verify/set (match QuarkyLab) — from Ares VLAN 20 leg
```bash
IDRAC=192.168.20.21
C="curl -sk --ciphers DEFAULT@SECLEVEL=0 -u root:<vaultwarden-pw>"
# READ: export System profile → GET the returned JID → grep the thermal attrs from the XML
$C -D - -X POST "https://$IDRAC/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ExportSystemConfiguration" \
   -H 'Content-Type: application/json' -d '{"ExportFormat":"XML","ShareParameters":{"Target":"System"},"ExportUse":"Default","IncludeInExport":"Default"}'
$C "https://$IDRAC/redfish/v1/TaskService/Tasks/<JID>" | grep -oE '<Attribute Name="ThermalSettings.1#[A-Za-z]+">[^<]*</Attribute>'
# SET only if not already Disabled/Default — success = MessageId SYS053:
$C -X POST "https://$IDRAC/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ImportSystemConfiguration" \
   -H 'Content-Type: application/json' \
   -d '{"ImportBuffer":"<SystemConfiguration><Component FQDD=\"System.Embedded.1\"><Attribute Name=\"ThermalSettings.1#ThirdPartyPCIFanResponse\">Disabled</Attribute><Attribute Name=\"ThermalSettings.1#ThermalProfile\">Default Thermal Profile Settings</Attribute></Component></SystemConfiguration>","ShareParameters":{"Target":"System"}}'
```

### Post-install verification (on the Jarvis host)
```bash
nvidia-smi                                     # expect 2× RTX 6000, driver 550.163.01
lspci -nn | grep -iE 'nvidia|mellanox'         # 2 NVIDIA + 1 Mellanox vs baseline above
ip -br link; ethtool <new-nic> | grep -i Speed # ConnectX → 10000Mb/s full duplex
# then the AUTO-RAMP proof under real GPU load (the ramp was NOT triggered by the CPU test):
watch -n 2 nvidia-smi                                                        # GPU temp/power
watch -n 5 'ipmitool sdr type fan; ipmitool sdr type temperature | grep -iE "inlet|exhaust"'
# EXPECT fans to climb above the ~3,800 floor as GPU temp rises. ABORT if GPU >85 °C and fans are NOT climbing.
```

---

## Related
- [[Compute/Dell R730 - ML Node]] — QuarkyLab (iDRAC 192.168.10.20, RTX 8000 48GB (installed 2026-07-01))
- [[Power Distribution]] — UPS A (Middle Atlantic)
- [[Infrastructure/Proxmox Cluster]] — cluster node table
