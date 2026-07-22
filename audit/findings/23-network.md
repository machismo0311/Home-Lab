# 23 — Network (Phase 2) — PARTIAL

**Scan:** 2026-07-22, read-only. Status: **PARTIAL** — the two network devices could not be
scraped non-interactively. This is itself recorded as a finding, not glossed (spec H5).

## EX3400 (192.168.10.50) — NOT PULLED (UNKNOWN)
- At scan the switch presented a **host-key conflict** (`Host key verification failed`), and with a
  clean known_hosts it rejected key auth: `Permission denied (publickey,password,keyboard-interactive)`.
  The switch is **password-auth only** (consistent with `runbooks/EX3400-SSH-Auth-Failure-RCA.md`),
  so `BatchMode` SSH cannot reach it and this audit will not do interactive/password login.
- **Not verified live this pass:** JunOS version (repo: 23.4R2-S7.4), the 7 VLANs, `native-vlan-id`
  placement, and `xe-0/2/0`/`xe-0/2/2`/`xe-0/2/3` 10G link state.
- **Action (Kyle):** reconcile the known_hosts entry, then pull once —
  `! ssh mason@192.168.10.50 'show configuration | display set | no-more'` — and diff against the
  repo. That diff is the network-layer staleness report and the argument for **Oxidized** (§30).

## OPNsense (192.168.10.1, VM 100 / pve2) — NOT TOUCHED (by design, H2)
- Read-only only, via API/dashboard — **no API credentials available to this audit**, so live
  state (Kea leases, firewall rules, gateway groups, running version) was **not** collected.
- The **25.7 vs 25.1.12** version conflict (adjudicated → 25.1.12) is settled from the docs/AAR,
  not re-read live here. If Kyle wants live confirmation: the OPNsense dashboard shows the version;
  do **not** change anything on VM 100.

## What IS known (from Phase 1 repo cross-check + live node NICs)
- **VLAN facts** (IDs 1/20/30/40/50/60/70, subnets, `native-vlan-id` at interface level) are
  internally consistent in the current docs **except** the stale "native-vlan-id not supported"
  copies — see `11-contradictions.md` S-VLAN.
- **Dual-homing live-confirmed indirectly:** QuarkyLab mounts `/data` from `192.168.30.187`
  (VLAN 30 NFS) — the VLAN-30 servers path is up and carrying NFS (`audit/live/quarkylab.txt`).
- Node reachability on VLAN 1 mgmt (`.10.x`) verified for all 8 hosts.

## Finding
- **F-N1 · MEDIUM — no automated network-config capture.** EX3400/OPNsense/UniFi configs are not
  pulled into git on a schedule; combined with the password-only/creds-gated access above, network
  config drift is invisible until something breaks. → **Oxidized/RANCID** (Tier-1, `30-gap-analysis.md`).
