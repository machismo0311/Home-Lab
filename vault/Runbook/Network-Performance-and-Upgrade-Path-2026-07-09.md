# Network Performance & Upgrade Path — km-cluster storage fabric

**Date:** 2026-07-09
**Author context:** written after fixing QuarkyLab's 1G→10G bottleneck. Scope = the 10G storage fabric (VLAN 30) linking **QuarkyLab**, **Jarvis**, **Randy** through the **EX3400**.
**Related:** [[VLAN30-Migration-Report-2026-07-02]], project memory `project-homelab` (10G fabric section).

---

## TL;DR (for future me)

- Tonight QuarkyLab was moved off a **1 GbE** uplink onto **10 GbE**. Measured **9.40 Gbit/s** QuarkyLab→Randy — that is **10G line rate** (TCP overhead eats the last ~6%). ~10× the old ceiling.
- **The network is no longer the bottleneck. Randy's spinning disks are.** For *real* storage throughput beyond ~1.5–2.5 GB/s sequential (far less for random/PBS), the lever is **NVMe on Randy**, not faster NICs.
- **Jumbo frames** are possible on the whole path (NICs 9600/9900, switch 9216) but they **do not raise peak bandwidth** — we're already at line rate. They only cut CPU per GB. Optional.
- **40 GbE is cheaper than you'd think:** the EX3400 has **two unused 40G QSFP+ ports**, and **Randy + Jarvis ConnectX-3 cards are already 40G-capable** (PCIe Gen3). But 40G to Randy is wasted until Randy's storage is faster.
- **QuarkyLab is the odd one out:** its 10G is an *onboard PCIe Gen2* NIC (~20G ceiling on that card). 40G on QuarkyLab needs an add-in ConnectX-3/4 in a Gen3 slot.

---

## 1. What changed tonight (2026-07-09)

QuarkyLab ran **everything** — VLAN 1 mgmt *and* VLAN 30 storage — over a single **1 GbE** port (`nic2`), with a saturated RX ring (~12.8k `rx_discards`). Its 10G DAC was physically plugged in (green lights) but:
1. the 10G port (`nic0`) was **administratively down** in Linux (no `auto nic0` in `/etc/network/interfaces`), and
2. `vmbr0` was bridged to the **1G** `nic2`; separately
3. the switch port `xe-0/2/3` was an **unconfigured access port** (default VLAN only, no `servers`/VLAN 30 tag).

**Fix:** (a) switch — made `xe-0/2/3` a trunk (`native-vlan-id 1` + `vlan members [ default servers ]`) matching the old port; (b) host — added `auto nic0`, moved `bridge-ports nic2 → nic0`. Applied via a detached self-rollback script. Verified `nic0 @ 10000 Mb/s` in `vmbr0`, VLAN 1 + VLAN 30 + gateway + egress all OK. The 1G port `nic2`/`ge-0/0/24` is now free.

> ⚠️ **Lesson:** a link/green-light only proves Layer 1. Always verify the **switch-port VLAN membership** before moving a bridge uplink — the two ports were not equivalent, and cutting over blind would have killed VLAN 30 + the default route (gateway lives on VLAN 30).

---

## 2. Measured results (the baseline)

| Test | Path | Tool | Result |
|---|---|---|---|
| QuarkyLab → Randy | `192.168.30.179 → 192.168.30.187:5201`, VLAN 30 | `iperf3 3.18`, 4 streams, 10 s, MTU 1500 | **9.40 Gbit/s** sender / **9.39** receiver, **0 retransmits** |
| (old 1G ceiling) | same, on `nic2`/`ge-0/0/24` | — | ~0.94 Gbit/s |

**How it was run:**
```bash
# on Randy (target): one-shot server as a detached unit so ssh logout can't kill it
ssh randy 'systemd-run --collect --unit=iperf-srv iperf3 -s -1 -p 5201'
ssh randy 'ss -ltn | grep 5201'      # confirm listening before testing

# on QuarkyLab (source): 4 parallel streams, 10 s, over VLAN 30
ssh quarkylab 'iperf3 -c 192.168.30.187 -p 5201 -t 10 -P 4'
```
`iperf3` (v3.18) was installed on all three nodes tonight (`apt-get install -y iperf3`).

**Interpretation:** 9.4 Gbit/s with **zero retransmits** = a clean, saturated 10G link. There is no more headroom to extract from a 10G port at MTU 1500 — this is the ceiling.

---

## 3. Current fabric (as of 2026-07-09)

| Node | Chassis | CPU | 10G NIC | NIC PCIe | Switch port | Link |
|---|---|---|---|---|---|---|
| **QuarkyLab** | Dell R730 | 2× E5-2699 v4 (44c/88t) | onboard **BCM57800** (bnx2x) | **Gen2 ×8** (~26 Gb/s card ceiling) | `xe-0/2/3` | 10 GbE ✅ |
| **Jarvis** | Dell R730 | 2× E5-2687W v4 (24c/48t, 3.0 GHz) | **ConnectX-3** MT27500 | **Gen3 ×8** (~63 Gb/s) | `xe-0/2/2` | 10 GbE ✅ |
| **Randy** | SuperMicro X10DRU-i+ | 2× E5-2690 v3 (24c/48t) | **ConnectX-3** MCX312A dual-port | **Gen3 ×8** (~63 Gb/s) | `xe-0/2/0` | 10 GbE ✅ |

**Switch — Juniper EX3400-48P** (Junos 23.4R2-S7.4), 264 Gbit/s non-blocking:
- **PIC 0:** 48× 1GbE Base-T (`ge-0/0/0..47`)
- **PIC 1:** **2× 40GbE QSFP+** (`et-0/1/0`, `et-0/1/1`) — **both FREE / unused**
- **PIC 2:** 4× 10GbE SFP+ (`xe-0/2/0..3`) — `0` Randy, `2` Jarvis, `3` QuarkyLab, **`xe-0/2/1` FREE**
- Jumbo: supports MTU up to **9216**; currently all ports at default **1514**.

**Spare NIC ports (for bonding):** QuarkyLab `nic1` (2nd onboard SFP+), Jarvis `enp132s0d1` (2nd ConnectX-3 port), Randy `nic2` (2nd ConnectX-3 port). All currently down/uncabled.

---

## 4. Hardware ceilings — the real "max output"

### PCIe (the hard limit per card)
| Link | Raw | Usable | Verdict |
|---|---|---|---|
| PCIe 2.0 ×8 | 32 Gb/s | ~26 Gb/s | QuarkyLab onboard NIC → caps ~2×10G (20G bond) max on that card |
| PCIe 3.0 ×8 | 63 Gb/s | ~56 Gb/s | Randy/Jarvis ConnectX-3 → **40G ready today** |
| PCIe 3.0 ×16 | 126 Gb/s | ~110 Gb/s | needed for 100G (ConnectX-4/5). R730 & X10DRU have free Gen3 ×16 slots |

### CPU — **not** the bottleneck
All three are dual-socket Xeon E5 v3/v4 (24–88 threads). With multi-stream + RSS these push 40G easily; even a single tuned TCP flow does ~15–25 Gb/s per core here. CPU won't gate 40G, and likely not 100G with jumbo + RSS.

### Storage — **this is the actual ceiling for Randy**
Randy `datastore` = **3× RAIDZ2 vdevs of 6× Toshiba 10K SAS** (18 spindles, 4 data + 2 parity per vdev), 128 GB RAM ARC.
- **Sequential read:** ~800 MB/s per vdev × 3 ≈ **2.4 GB/s theoretical (~19 Gb/s)**; realistically **1.5–2 GB/s (12–16 Gb/s)** with RAIDZ2 overhead/fragmentation.
- **Random / PBS chunk restore:** far lower — 10K SAS random IOPS scale with *vdev count* (only 3), so fragmented restores can drop well under 1 GB/s. ARC caches hot chunks + metadata.
- **Bottom line:** Randy's disks deliver ~**12–20 Gb/s sequential at best, much less random**. So 10G already carries most of what the pool can source sequentially; a faster NIC does nothing for cold reads until the storage backend is faster.

### Per-node practical max (today's hardware)
| Node | NIC card ceiling | Realistic workload ceiling |
|---|---|---|
| QuarkyLab | ~20 Gb/s (bond both onboard SFP+) / 40G+ with add-in card | GPU/ML local; NFS client — network-bound, so ~10–20G useful |
| Jarvis | 40 Gb/s (existing ConnectX-3) | LLM node; NFS client — ~10–20G useful |
| Randy | 40 Gb/s (existing ConnectX-3) | **storage-bound ~12–20 Gb/s sequential** until NVMe added |

---

## 5. Jumbo frames — the free tier

**Can the fabric do it?** Yes. NIC max MTU: QuarkyLab 9600, Randy 9600, Jarvis 9900; EX3400 up to 9216.

**Will it help?** Not for peak bandwidth — we're already at 10G line rate. Jumbo's only benefit here is **lower CPU per gigabyte** (fewer packets/interrupts), which matters if a node is CPU-bound during big sustained PBS/NFS transfers. Modest on these Xeons.

**Pros:** lower CPU during bulk transfer; slightly better efficiency; free.
**Cons:** MTU mismatch **silently black-holes large frames** — must be *all-or-nothing* across the entire VLAN 30 L2 segment; must not break egress via the OPNsense gateway (`.30.1`, MTU 1500); operational fiddliness for near-zero throughput gain.

**Path to enable (maintenance window, iDRAC/console as backup):**
1. **Switch** (all three 10G trunk ports):
   ```
   set interfaces xe-0/2/0 mtu 9216
   set interfaces xe-0/2/2 mtu 9216
   set interfaces xe-0/2/3 mtu 9216
   commit confirmed 5   → verify → commit
   ```
2. **Each server** — set MTU 9000 on the physical NIC **and** the bridge **and** the VLAN 30 sub-interface *together* (in `/etc/network/interfaces`, add `mtu 9000` to `nic0`/`nic3`/`enp132s0`, `vmbr0`, and `vmbr0.30`/`vmbr1`), then `ifreload -a`. Use the same detached self-rollback approach as the 10G cutover.
3. **Validate** (must succeed with DF bit set — proves no fragmentation anywhere):
   ```bash
   ping -M do -s 8972 192.168.30.187   # from each node to each peer
   ```
   Then re-run the `iperf3` test and compare **CPU%**, not Gb/s.

> If any `ping -M do -s 8972` fails, back out immediately — something on the path is still 1500.

---

## 6. Upgrade tiers — what would actually make a difference

Ordered by value-for-effort, **not** by raw speed.

### Tier 0 — Jumbo frames — *free, low ROI*
CPU efficiency only. See §5. Do it only if chasing CPU headroom on heavy backup windows.

### Tier 1 — LACP 2×10G bonds — *cheap, helps concurrency*
Every node has a spare NIC port. Bond both ports (Linux `bond`/`balance-*` + switch `ae` LAG) → **20 Gb/s aggregate**, but **per-flow still 10 Gb/s** (a single backup stream won't exceed 10G). Real benefit: multiple nodes hammering Randy at once no longer contend on one 10G port.
- **Constraint:** only **one** free 10G switch port (`xe-0/2/1`). To bond *all* nodes you'd first **channelize a 40G QSFP+ into 4×10G** (`et-0/1/0` → `xe-0/1/0:0..3`), yielding plenty of 10G ports.
- **Cost:** DAC cables + config. **Effort:** medium. **Cost:** $.

### Tier 2 — 40 GbE for Randy (+ one node) — *moderate, but storage-gated*
The EX3400's **two free 40G QSFP+ ports** + Randy/Jarvis's **already-40G-capable ConnectX-3** make this the cheapest big-number jump:
- Randy → `et-0/1/0` (40G), and one heavy client (Jarvis) → `et-0/1/1` (40G). QuarkyLab stays 10G *or* gets a ConnectX-3 add-in card (~$25 used, Gen3 slot).
- Alternative: a **direct 40G Randy↔Jarvis** DAC (no switch port used) for a dedicated replication/storage path.
- **Reality check:** per-flow 40G is **wasted on Randy until its storage is faster** (§4 — disks cap ~12–20 Gb/s sequential). Pair with Tier 3 or it's mostly a benchmark trophy.
- **Cost:** QSFP+ DACs ($15–30 ea), maybe one ConnectX-3 card. **Effort:** medium. **Cost:** $–$$.

### Tier 3 — Faster storage on Randy — *the actual bottleneck fix*
This is what makes bytes move faster in real life:
- **ZFS special vdev** (mirrored enterprise NVMe) for metadata + small blocks → massively speeds PBS chunk/metadata access.
- **L2ARC** (NVMe read cache) for hot working set; **SLOG** (power-loss-protected NVMe) for sync writes (NFS).
- Or a **dedicated NVMe pool** for the PBS datastore (PBS is random/chunky — loves flash).
- **Effect:** unlocks the NIC you already have (and any future 40G). **Effort:** medium–high. **Cost:** $$ (enterprise NVMe + possibly an HBA/NVMe carrier; R730/X10DRU support U.2 or PCIe NVMe).

### Tier 4 — 25/100 GbE fabric — *overkill until all-NVMe*
- **NICs:** ConnectX-4/5 (Gen3 ×16) — 25G or 100G.
- **Switch:** the EX3400 can't do 25/100G; you'd add a **Mellanox SN2010 (18×25G + 4×100G)** or a used 100G switch.
- **Only worth it** if storage becomes all-NVMe (Tier 3 at scale) and you're moving datasets where 10/40G genuinely limits research workflows. **Effort:** high. **Cost:** $$$.

---

## 7. Recommendation (priority order)

1. **Do nothing urgent** — tonight's 10G cutover already removed the one real bottleneck; you're at line rate with zero retransmits.
2. **If you want efficiency:** Tier 0 jumbo (low effort, CPU savings only).
3. **The real lever for "faster transfers":** Tier 3 — **NVMe on Randy** (special vdev / L2ARC / SLOG, or NVMe PBS datastore). This, not faster NICs, is what makes storage feel faster.
4. **If concurrent multi-node backups congest:** Tier 1 LACP, or Tier 2 40G on Randy — but **pair 40G with Tier 3** or it won't deliver.
5. **100 GbE (Tier 4):** only if you commit to all-NVMe research storage.

**One-line version:** *You just uncorked the network. The next real gain is disks on Randy (NVMe), not a bigger pipe. 40G is available almost for free (free switch ports + capable cards) but is pointless until the disks can feed it.*

---

## Appendix A — throughput test recipe (repeatable)
```bash
# target (Randy): detached one-shot server
ssh randy 'systemctl reset-failed iperf-srv 2>/dev/null; systemctl stop iperf-srv 2>/dev/null; \
           systemd-run --collect --unit=iperf-srv iperf3 -s -1 -p 5201'
ssh randy 'ss -ltn | grep 5201'                          # confirm listening
# source: single-stream (per-flow ceiling) then 4-stream (aggregate)
ssh quarkylab 'iperf3 -c 192.168.30.187 -p 5201 -t 10'        # ~9.4 Gb/s single stream expected
ssh quarkylab 'iperf3 -c 192.168.30.187 -p 5201 -t 10 -P 4'   # SUM ~9.4 Gb/s (link saturated)
ssh quarkylab 'iperf3 -c 192.168.30.187 -p 5201 -t 10 -R'     # reverse direction
```

## Appendix B — EX3400 login & port map
- SSH: `mason@192.168.10.50` (password in Vaultwarden; the `switch`/`ex3400` alias sets the legacy Kex/HostKey algos Junos needs). Use `commit confirmed` for any risky change.
- 10G: `xe-0/2/0`=Randy, `xe-0/2/2`=Jarvis, `xe-0/2/3`=QuarkyLab, `xe-0/2/1`=**free**.
- 40G: `et-0/1/0`, `et-0/1/1` = **both free** (PIC 1, 2×40G QSFP+).
- Trunk template (matches the working node ports): `native-vlan-id 1` + `interface-mode trunk` + `vlan members [ default servers ]`.

## Appendix C — MTU capability snapshot (2026-07-09)
| Device | Max MTU | Current |
|---|---|---|
| QuarkyLab `nic0` (bnx2x) | 9600 | 1500 |
| Randy `nic3` (mlx4) | 9600 | 1500 |
| Jarvis `enp132s0` (mlx4) | 9900 | 1500 |
| EX3400 xe-/et- ports | 9216 | 1514 |
