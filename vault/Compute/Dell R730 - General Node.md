# 🖥️ Dell R730 — Jarvis (General / LLM Node)
**Tags:** #compute #dell #r730 #llm
**Related:** [[Compute/Dell R730 - ML Node]] · [[Infrastructure/Proxmox Cluster]] · [[Power Distribution]]

---

## Status: 🟢 Online — km-cluster node (no GPU yet; 2× RTX 6000 staged)

- **Host IP (mgmt, VLAN 1):** 192.168.10.31 · **Service IP (VLAN 30):** 192.168.30.31 — dual-homed 2026-07-02 (see [[Runbook/VLAN30-Migration-Report-2026-07-02]])
- **iDRAC:** 192.168.10.21 (root/calvin)
- Member of km-cluster (PVE 9.2.3); Headscale 100.64.0.6
- **Scrutiny collector** installed 2026-07-02 (reports `sda` SMART to hub `192.168.10.183:8080`, 6h timer)
- Kernel pinned to **6.14.11-9-pve** (GRUB_DEFAULT; NOT proxmox-boot-tool) for the NVIDIA GPU stack — do not upgrade/change
- **2× RTX 6000 48GB planned** (both cards in hand; QuarkyLab's old RTX 6000 + a new one per the 2026-06-30 GPU plan). GPU software stack BUILT 2026-07-01 (kernel 6.14.11-9-pve, NVIDIA 550.163.01 DKMS, Ollama v0.31.1 → /opt/models). Physical install gated on Dell N08NH aux power cables (2 sets) + R730 GPU riser kit.

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
| **GPU** | none installed — 2× RTX 6000 48GB planned (SW stack ready: 6.14.11-9-pve + NVIDIA 550.163.01) |
| Storage | pve LVM 56GB — sda (186GB ST200FM0053 SAS SSD) added to VG 2026-06-22 after disk-full during upgrade; **/opt/models 98G LV** (2026-07-01) for LLM weights |
| NICs | 4× 1G onboard |
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

## Pending — 2× RTX 6000 install

- Awaiting Dell **N08NH** GPU aux power cables (2 sets) + R730 GPU riser kit.
- Kernel/driver/Ollama already staged (2026-07-01): `dkms status` shows `nvidia/550.163.01, 6.14.11-9-pve` installed; `nvidia-smi` will report devices once cards are seated.
- Headscale Phase 2: QuarkyLab + Fernanda's Mac must migrate together — do not migrate one without the other.

---

## Fan / Thermal — GPU install

Same platform as QuarkyLab, so expect the **same ~3,800 RPM idle fan floor** once the 2× RTX 6000 are seated — that is **normal and inherent**, not a fault, and is not safely reducible (full 2026-07-04 investigation + iDRAC-8 SCP export/import procedure in [[Compute/Dell R730 - ML Node]] → Thermal / Fan Control). The floor already auto-ramps under load.

Replicate QuarkyLab's proven-good GPU thermal config on Jarvis (iDRAC **192.168.20.21**, VLAN 20, root pw in Vaultwarden) — verify/set via SCP export/import from Ares' `enp0s31f6.20`:
- `ThermalSettings.1#ThirdPartyPCIFanResponse` = **Disabled** ← the key GPU setting: stops the RTX cards from triggering a loud fixed fan ramp.
- `ThermalSettings.1#ThermalProfile` = **Default Thermal Profile Settings** (not Max Performance).

Do **not** use manual static fan control (`ipmitool raw 0x30 0x30`) — it disables auto-ramp and is unsafe with GPUs. iDRAC cannot read GPU temp on any R730; verify GPU thermals directly with `nvidia-smi` under first load.

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
