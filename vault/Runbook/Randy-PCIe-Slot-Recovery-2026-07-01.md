# Randy — PCIe Slot Failure & Recovery

**Date:** July 1, 2026
**Node:** Randy (SuperMicro CSE-219U / X10DRU-i+)
**Severity:** High — node down; PBS + ZFS `datastore` + Jellyfin offline; corosync quorum reduced
**Type:** Incident report + recovery runbook
**Author:** Kyle Mason
**Related:** [[Runbook/randy-commissioning-runbook]] · [[Runbook/Recovery Procedures]] · [[Infrastructure/Storage]] · [[Infrastructure/Proxmox Cluster]]

---

## Summary

After a power cycle (and a routine CMOS battery replacement), Randy would not boot — "no boot device." The **AVAGO 3108 MegaRAID controller was not detected by the BIOS at all.** Since that one card owns both the RAID-1 boot mirror **and** every ZFS data drive (via JBOD), an undetected controller meant zero storage visible to firmware.

**Root cause: a failed PCIe slot**, not the card. In the bad slot the card got power but no working PCIe link, so its firmware never initialized and it never enumerated. Moving the AVAGO to a known-good slot restored detection; Randy booted normally with the boot mirror and ZFS pool fully intact. **No data loss.**

---

## Symptoms

- POST showed only the Mellanox `MLNX FlexBoot 3.4.306` OpROM banner — the AVAGO MegaRAID banner never appeared.
- Boot menu offered only: `UEFI: Built-in EFI Shell`, `MLNX FlexBoot 3.4.306`, `Enter Setup` — no RAID volume / Proxmox entry.
- EFI Shell `map -r` → "cannot find required map name" (zero block devices), even after `reconnect -r`.
- No `AVAGO` / SAS entry anywhere under BIOS → Advanced → PCIe/PCI/PnP Configuration.

## Root Cause

The **PCIe slot the AVAGO 3108 had always lived in had failed.** In that slot the card received *power* but had no working PCIe data link:

| Location | Card LEDs (next to the SFF-8643 SAS connectors) | Meaning |
|---|---|---|
| Original (bad) slot | Solid green **+ solid red**, no blink | Powered, but firmware never initialized |
| Known-good slot | **Blinking green heartbeat (D13)**, no red fault | Firmware running normally |

Because every disk sits behind the AVAGO (boot mirror + all JBOD data drives), a controller that never enumerates = "no boot device" and an empty installer/EFI disk list.

The CMOS battery swap was a **red herring** for the boot failure. It reset the BIOS to defaults (re-enabling PXE OpROMs), which sent troubleshooting down an OpROM-exhaustion path — that was not the cause.

## What was ruled out (and why)

- **OpROM / option-ROM shadow exhaustion** — disabling onboard LAN PXE, disabling the Network Stack, and switching slots to EFI made no difference. A card whose slot works enumerates and appears in the BIOS inventory *regardless* of OpROM policy. This one never appeared → not an OpROM problem.
- **Dead card** — the card powered up and ran a healthy blinking-green heartbeat the moment it was moved to a good slot.
- **Corrupt Proxmox install** — the existing install booted untouched once the controller was seen. Nothing was reinstalled. (Reinstalling would have been the wrong move — it would not have fixed a controller the firmware couldn't see, and risked the ZFS pool.)

> **Key lesson:** If the MegaRAID banner is missing at POST, the controller is not detected. That is a **physical/slot** problem — do not chase BIOS OpROM/boot-order settings.

## Resolution

1. **Full power-down** — pulled *both* PSU cords. Redundant PSUs keep the board on standby otherwise.
2. **Swap test to isolate card vs. slot** — moved the AVAGO (bare, no SAS cables) into the Mellanox's proven-good slot → blinking-green heartbeat + banner. Card confirmed healthy; slot confirmed dead.
3. **Committed the fix** — permanently relocated the AVAGO 3108 to the good (former Mellanox) slot; relocated the Mellanox ConnectX-3 to another working slot; re-routed the two internal SFF-8643 SAS cables to reach the card's new position (cut one zip tie for slack); reconnected both SAS cables to the backplane.
4. **BIOS** — Load Optimized Defaults, Boot Mode = Dual.
5. Randy booted straight into Proxmox VE.

---

## Post-Recovery Verification — 2026-07-01

Full health check over `ssh randy` (root@192.168.10.187). All green.

| Check | Result |
|---|---|
| AVAGO 3108 | Detected at PCI `82:00.0`, FW 4.620.00-5026 |
| Boot RAID-1 ("Boot" VD) | **Optimal** — both ST200FM0053 SSDs Online (0:0, 0:1) |
| JBOD data drives | 22 present — 18× Toshiba AL15SEB18EQ 1.636T (0:2–0:19) + 4× Seagate ST2000NX0423 1.819T SATA (0:20–0:23). JBOD survived reboot (no re-enable needed) |
| ZFS pool `datastore` | **ONLINE, 0 errors**, scrub clean. 4 vdevs: raidz2-0/1/2 (6× Toshiba each) + raidz2-3 (4× Seagate) |
| Pool capacity | SIZE 36.7T raw · ~23T usable · 19.5G used (0% cap) |
| Root FS | `/dev/mapper/pve-root` 55G, 17% used |
| Cluster | Quorate — 7 nodes / 7 votes |
| Versions | kernel 7.0.12-1-pve · pve-manager 9.1.1 |
| Services | proxmox-backup(-proxy), jellyfin, pve-cluster, corosync, pvedaemon all active. Ports 8007 (PBS) + 8096 (Jellyfin) listening. No failed units |
| 10G Mellanox | nic3 **UP @ 10000Mb/s full duplex**, link detected (carries vmbr0 → .187). ConnectX-3 at `84:00.0`. 2nd port down/uncabled (normal) |
| LSI 9207-8e | Present at `85:00.0` (for future DS4246) |
| PCIe health | No AER / correctable / uncorrectable errors |
| Thermals | CPU1 42°C · CPU2 41°C · System 30°C · Peripheral 36°C · VRMs 37°C |
| Fans | FAN1/2/7/8 @ 4200 RPM OK. FAN3–6 "no reading" = unpopulated headers (normal) |
| RAM | 125Gi total, 4.7Gi used, 121Gi available |

**The 10G card was never faulty** — it only appeared "down" because Randy itself was down. It is up and passing traffic.

---

## Runbook — "Randy won't boot / no boot device"

Fast triage for next time:

1. **Console/IPMI — watch POST. Is the AVAGO MegaRAID banner present?**
   - **Yes** → controller is seen; this is a boot-order/entry problem. Use Boot Override to pick the RAID volume, or in EFI Shell: `map -r` then `FS0:\EFI\proxmox\grubx64.efi`.
   - **No** → controller not detected → **physical, not settings.** Go to step 2.
2. **Power fully off (pull both PSU cords).** Open chassis. Find the AVAGO's **D13 heartbeat LED** (next to the two SFF-8643 SAS connectors, near the small buzzer):
   - **Blinking green** = card alive → reseat card + riser; if still undetected, the **slot is bad** → move the card to a known-good slot.
   - **Solid / no blink** = firmware not running → almost always a bad slot or unseated riser → swap into a known-good slot to prove card vs. slot.
3. **Do not chase BIOS OpROM / Network Stack / boot-order settings for a _detection_ failure.** A seated, working card always enumerates regardless of OpROM policy.
4. **Data safety** — the ZFS `datastore` pool is portable: importable on any HBA with `zpool import datastore`. Only the boot OS is tied to the MegaRAID RAID-1 mirror. Never Initialize/Clear/Delete/import-Foreign the boot VD without confirming first.

## Hardware facts to remember

- The AVAGO 3108 (AOC-S3108L-H8iR, SAS3108 "Invader") is a **standard low-profile PCIe 3.0 x8 card** — slot-powered, **no separate power cable**. The only cables on it are the two internal mini-SAS HD (SFF-8643) data cables.
- LED map: LED1 SAS activity (green blink) · LED6 SAS fault (red = SAS error) · **D13 system heartbeat (green blink = firmware healthy; solid/off = not running)**.
- "Battery Status: Missing" in the MegaRAID utility is **normal** — the optional CacheVault/Supercap is not fitted.
- Post-recovery PCI map: AVAGO `82:00.0` · ConnectX-3 `84:00.0` · LSI 9207-8e `85:00.0`.

## Follow-ups

- [ ] **Mark the original (dead) PCIe slot** on the chassis so it is never reused.
- [ ] Re-secure the re-routed SAS cables with a fresh zip tie (one was cut for slack).
- [ ] Keep an eye on the CMOS battery — the whole event started with it going flat.

## Quick reference

```bash
ssh randy                       # root@192.168.10.187
zpool status datastore          # pool health
storcli64 /c0/vall show         # boot VD (RAID-1)
storcli64 /c0/eall/sall show    # all physical drives / JBOD state
pvecm status                    # cluster quorum
```
