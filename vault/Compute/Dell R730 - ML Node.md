# 🖥️ Dell R730 - QuarkyLab (ML Node)
**Tags:** #compute #dell #r730 #cuda #ml
**Related:** [[Compute/Dell R730 - General Node]] · [[Infrastructure/Proxmox Cluster]] · [[Power Distribution]] · [[Infrastructure/QuarkyLab Storage]] · [[Runbook/QuarkyLab-Phase04-GPU-Sharing-2026-07-02]] · [[00 - Homelab MOC]]

---

## Status: 🟢 Online - km-cluster node (RTX 8000 48GB ML - installed 2026-07-01)

- **Host IP (mgmt, VLAN 1):** 192.168.10.179 · **Service IP (VLAN 30):** 192.168.30.179 - dual-homed 2026-07-02 (corosync/mgmt/monitoring on VLAN 1; NFS `/data` + PBS + egress on VLAN 30). See [[Runbook/VLAN30-Migration-Report-2026-07-02]].
- **iDRAC:** 192.168.20.20 (VLAN 20 since 2026-07-03; root / creds in Vaultwarden - reach from Ares `enp0s31f6.20`)
- Member of km-cluster (PVE 9.2.3)
- Hosts **Wazuh SIEM VM 104** (192.168.10.184)
- **Scrutiny collector** installed (reports to hub at 192.168.10.183:8080)
- SSH: `ssh quarkylab` (via `fernanda@quarkylab` key, id_ed25519 on Ares)
- **RTX 8000 48GB installed 2026-07-01** (per the 2026-06-30 GPU plan): the RTX 6000 was swapped out for the RTX 8000; nvidia-smi reports 46080 MiB on driver 550.163.01 / kernel 6.14.11-9-pve. Driver-free swap (both Turing TU102). The freed RTX 6000 was subsequently installed in Jarvis (2026-07-04).

> [!WARNING] Kernel pin
> Kernel **must** stay on `6.14.11-9-pve` - `GRUB_DEFAULT` is pinned; 6.17+ breaks NVIDIA 550. Never run kernel upgrades or change the GRUB default on QuarkyLab. NVIDIA 550.163.01 verified working post-upgrade.

> [!WARNING] Wazuh VM 104 has no qemu-guest-agent
> A QuarkyLab host reboot **hard-stops** VM 104 (unclean), so `wazuh-indexer` (OpenSearch) comes back unhealthy and the dashboard returns **503**. After any QuarkyLab reboot, power-cycle the VM from the host and wait ~4 min:
> ```bash
> qm stop 104 && qm start 104
> ```
> **Healthy state** (check from the host): dashboard root `https://192.168.10.184/` → **302 → /app/login** (login page = 200); manager API `:55000` → 401. (Indexer `:9200` reads `000`/refused from the LAN - that's normal, it binds internally.)
>
> **Permanent fix:** install the guest agent *inside* the VM - `apt install -y qemu-guest-agent` (Debian/Ubuntu) or `dnf install -y qemu-guest-agent` (RHEL/Amazon Linux), then `systemctl enable --now qemu-guest-agent`; on the host `qm set 104 --agent enabled=1` + one cold `qm stop 104 && qm start 104` to attach the virtio-serial channel. Then host reboots shut it down gracefully. `onboot=1` is set.

---

## Hardware Specs

| Component | Spec |
|---|---|
| Model | Dell PowerEdge R730 |
| Hostname | QuarkyLab |
| Service Tag | **(in ops vault)** |
| Form Factor | 2U |
| Rack Position | U15–U16 |
| **CPU** | 2× Intel Xeon E5-2699 v4 (44c / 88t total) |
| CPU Base Clock | 2.2 GHz |
| **RAM** | 512 GB LRDIMM ECC DDR4 |
| **GPU** | NVIDIA Quadro RTX 8000 48GB GDDR6 ECC (driver 550.163.01) - installed 2026-07-01 (swapped from RTX 6000) |
| NICs | 4× 1G onboard |
| **Storage controller** | Dell **PERC H330 Mini** (LSI SAS-3 3008), RAID-Mode + **JBOD ON** → drives pass through for ZFS; 8-bay **BP13G+** backplane. `storcli64` at `/usr/local/bin` |
| **Boot / OS** | `sda` (slot 0), 2TB Hitachi, `pve` LVM (`pve-root` 96G + `pve-data` thin → **Wazuh VM 104**) |
| **`workspace` ZFS pool** | **6-wide raidz1** (5× 2TB SATA + 1× 2TB SAS), **10.9 TB raw** / ~9.1 TB usable, lz4, `/workspace` + **1× 2TB SAS hot spare** (slot 7). Full slot/serial map: [[Infrastructure/QuarkyLab Storage]] · expansion history: [[Runbook/QuarkyLab-Storage-Expansion-2026-07-13]] |
| Remote Mgmt | iDRAC 8 (192.168.20.20, VLAN 20 since 2026-07-03) |
| Depth | ~28" - **rear panel removed** from NetFRAME CS9000 |

---

## Purpose

- the researcher's ML workloads / **DUNE agent** (RAG pipeline over the DUNE experiment codebase)
- CUDA compute (PyTorch, TensorFlow, JAX), training / fine-tuning
- Vector store (ChromaDB or Qdrant - TBD)

---

## GPU - Quadro RTX 8000 Detail (installed 2026-07-01)

| Field | Value |
|---|---|
| VRAM | 48 GB GDDR6 ECC (46080 MiB reported) |
| CUDA Cores | 4608 |
| Tensor Cores | 576 (2nd gen) |
| TDP | ~250W |
| Driver | NVIDIA 550.163.01 (CUDA 12.x) |

> [!NOTE] RTX 8000 installed 2026-07-01
> Per the 2026-06-30 plan, QuarkyLab now runs the **RTX 8000 48GB**; its former RTX 6000 was subsequently installed in Jarvis (2026-07-04). Both are Turing TU102 - the swap was driver-free (same 550.163.01 / 6.14.11-9-pve stack), verified with nvidia-smi (46080 MiB). See [[Compute/Dell R730 - General Node]].

> [!WARNING] Power Draw
> RTX 8000 under full load = ~260W; with dual Xeons this node can draw 500W+. Runs on **UPS A** (Middle Atlantic UPS-OL2200R, the ML bus). See [[Power Distribution]].

---

## CUDA Environment

```bash
nvidia-smi                       # verify GPU + driver 550.163.01
conda create -n ml python=3.11
conda activate ml
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

---

## iDRAC Access

```bash
https://192.168.20.20                                   # Web UI, VLAN 20 (root / creds in Vaultwarden - reach from Ares enp0s31f6.20)
racadm -r 192.168.20.20 -u root -p "$IDRAC_PASS" getsysinfo
racadm -r 192.168.20.20 -u root -p "$IDRAC_PASS" getsel        # event log
```

---

## Thermal / Fan Control - investigated & measured 2026-07-04

**Bottom line: the ~3,800 RPM idle fan floor is inherent to this R730 GPU config and is NOT reducible by any auto-ramp-preserving setting. Leave it stock.** The only knob that lowers it - manual static `ipmitool raw 0x30 0x30 0x02 …` - disables auto-ramp and is unsafe on a GPU node; do **not** use it here.

Current committed thermal config (verified via SCP export 2026-07-04):

| Attribute (`ThermalSettings.1#…`) | Value | Note |
|---|---|---|
| `ThermalProfile` | `Default Thermal Profile Settings` | Already optimal - not Max Performance |
| `ThirdPartyPCIFanResponse` | `Disabled` | **Correct for GPUs** - suppresses the loud fixed third-party-card fan ramp |
| `MinimumFanSpeed` | `15` (%) | |
| `FanSpeedOffset` | `Low Fan Speed` | |
| `AirExhaustTemp` | `70` (°C) | |

Tested 2026-07-04 and **ruled out** as levers (all reverted afterward):
- `ThirdPartyPCIFanResponse` toggled Enabled↔Disabled via `ipmitool raw 0x30 0xce` → **zero** fan change. ⚠ the ipmitool bit reads INVERTED vs the iDRAC label: `ipmitool raw 0x30 0xce 0x01 0x16 0x05 0x00 0x00 0x00` returning `…05 00 01 00 00` == iDRAC `Disabled`.
- `MinimumFanSpeed` 15→10 → zero change (fans already idle above the floor).
- `FanSpeedOffset` `Low Fan Speed`→`Off` → zero change.
- **CPU load test** (88-worker burn, loadavg 67.8): fans held 3,720–3,960 RPM, exhaust rose only **33→34 °C** - airflow is so generous no ramp was needed (limit 70 °C = huge headroom).

Auto-ramp is intact by design: these settings only set the floor/offset; the ramp loop (driven by CPU/exhaust temp - **iDRAC cannot read GPU temp on any R730**, so GPU heat is sensed indirectly via exhaust air) is untouched. Ambient inlet target < 25 °C; rear CS9000 panel removed - ensure wall clearance.

### Reading/changing thermal on this iDRAC 8 (fw 2.86)
`racadm` is not installed and this firmware exposes **no** Redfish `DellAttributes`/`Attributes` resource - use **SCP export/import**. iDRAC is on **VLAN 20 (192.168.20.20)**; the node can no longer reach its own iDRAC (routes out the VLAN 30 gw), so drive it **from Ares' wired VLAN 20 leg `enp0s31f6.20`** with legacy TLS. Root pw in Vaultwarden. `enp0s31f6` must be physically up (carrier=1) or VLAN 20 silently reroutes via WiFi→OPNsense and is firewalled off.

```bash
IDRAC=192.168.20.20
C="curl -sk --ciphers DEFAULT@SECLEVEL=0 -u "$IDRAC_USER:$IDRAC_PASS""      # SECLEVEL=0 required for iDRAC-8 TLS
# READ: export System profile → note the JID → GET the task; XML body carries ThermalSettings when Completed
$C -D - -X POST "https://$IDRAC/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ExportSystemConfiguration" \
   -H 'Content-Type: application/json' \
   -d '{"ExportFormat":"XML","ShareParameters":{"Target":"System"},"ExportUse":"Default","IncludeInExport":"Default"}'
$C "https://$IDRAC/redfish/v1/TaskService/Tasks/<JID>"
# WRITE: import one attribute → poll JID; success = MessageId SYS053, invalid value = RAC015 (no change). Applies live, no reboot.
$C -X POST "https://$IDRAC/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Oem/EID_674_Manager.ImportSystemConfiguration" \
   -H 'Content-Type: application/json' \
   -d '{"ImportBuffer":"<SystemConfiguration><Component FQDD=\"System.Embedded.1\"><Attribute Name=\"ThermalSettings.1#MinimumFanSpeed\">15</Attribute></Component></SystemConfiguration>","ShareParameters":{"Target":"System"}}'
```
`FanSpeedOffset` valid values on this fw: `Off`, `Low Fan Speed`, `High Fan Speed`, `Max Fan Speed` (the racadm "…Fan Speed Offset" strings are rejected → RAC015). Live in-band check on the host: `ipmitool sdr type fan`, `ipmitool sdr type temperature`, `nvidia-smi`.

---

## Chassis Intrusion / F1 POST Halt

> [!NOTE] Cover-removal F1 halt - FIXED 2026-07-02
> Opening the lid trips the chassis-intrusion switch; on the next POST the R730 shows `Alert! Cover was previously removed - Press F1 to continue` and **halts boot** waiting for a keypress. That prompt renders on the onboard **Matrox G200 VGA (0a:00.0)**, *not* the GPU - a monitor plugged into the RTX card shows a black "no signal" screen. This stalled the node during the 2026-07-01 RTX 8000 swap.
>
> **Fix (2026-07-02):** BIOS `MiscSettings.ErrPrompt` ("F1/F2 Prompt on Error") set to **Disabled** - POST no longer stops for non-fatal alerts. Verified after reboot: `ErrPrompt: Disabled`, kernel 6.14.11-9-pve, RTX 8000 present, Wazuh VM 104 auto-started. Intrusion is still recorded to the iDRAC SEL; it just no longer halts boot.

> [!TIP] Changing BIOS attributes on this iDRAC 8 - no racadm, use Redfish
> `racadm` is not installed anywhere. iDRAC moved to **VLAN 20 (192.168.20.20)** on 2026-07-03, and the node can no longer reach its own iDRAC (routes out the VLAN 30 gw) - so drive Redfish **from Ares' wired VLAN 20 leg `enp0s31f6.20`** with legacy TLS (`--ciphers DEFAULT@SECLEVEL=0`, required for the iDRAC-8 handshake). Root pw in Vaultwarden. Then reboot to apply:
> ```bash
> IDRAC=192.168.20.20
> C="curl -sk --ciphers DEFAULT@SECLEVEL=0 -u root:$IDRAC_PASS"
> B="https://$IDRAC/redfish/v1/Systems/System.Embedded.1/Bios"
> # 1) stage the attribute change (goes to Bios/Settings as pending)
> $C -X PATCH "$B/Settings" -H 'Content-Type: application/json' -d '{"Attributes":{"ErrPrompt":"Disabled"}}'
> # 2) create the BIOS config job - applies at next reboot
> $C -X POST "https://$IDRAC/redfish/v1/Managers/iDRAC.Embedded.1/Jobs" \
>   -H 'Content-Type: application/json' -d "{\"TargetSettingsURI\":\"$B/Settings\"}"
> # 3) after reboot verify:  $C "$B" | grep -i errprompt  →  "ErrPrompt":"Disabled"
> ```

---

## Related
- [[Compute/Dell R730 - General Node]] - Jarvis (iDRAC 192.168.20.21, LLM, 2× RTX 6000 24GB installed 2026-07-04, gpu-fan-control daemon)
- [[Power Distribution]] - UPS A (Middle Atlantic, ML bus)
- [[Infrastructure/Proxmox Cluster]] - GPU passthrough config
