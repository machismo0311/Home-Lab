# Runbook: VLAN 20 (BMC) Egress Clamp — Segmentation Phase 1.5

**Status:** PREPPED, awaiting go/no-go (2026-07-17). Scripts staged, dry-run validated,
nothing applied.
**Source:** AAR-2026-07-16 recommendation; the un-done half of `Security-VLAN-Segmentation-Phased-2026-07-03.md`.

## Why

VLAN 20 (OPNsense `opt1`, `192.168.20.0/24`, labelled "TRUSTED") hosts the BMCs —
QuarkyLab iDRAC .20, Jarvis iDRAC .21, Randy IPMI .22 — plus Ares' management leg
`.20.100`. Phase 1 moved the BMCs here and clamped INBOUND (LAN/Servers cannot reach
VLAN 20 except Ares). But the interface still carries its original "trusted admin"
OUTBOUND rules, so a **compromised BMC can reach VLAN 1, VLAN 30, and the internet**.
BMC firmware is a known attack surface (cf. the Supermicro/AMD advisories); a BMC that
can phone home or pivot into management is the risk this closes.

## Current state (opt1, read from live config 2026-07-17)

| # | Action | Dest | Note |
|---|---|---|---|
| 1 | PASS | 192.168.10.0/24 | trusted -> management (VLAN 1) |
| 2 | PASS | 192.168.30.0/24 | trusted -> servers (VLAN 30) |
| 3 | BLOCK | Local_Nets | trusted -> other VLANs |
| 4 | PASS | any | trusted -> internet |

Rules 1, 2, 4 are the exposure. Dry-run confirmed the change selects exactly these
three (type=pass on opt1) and touches none of the other 17 rules on other interfaces.

## Target state

Remove rules 1, 2, 4. Keep rule 3. Append a **block+log catch-all** on opt1. Result:
VLAN 20 -> internal is denied (rule 3 + catch-all), VLAN 20 -> internet is denied
(no pass + catch-all), and every dropped attempt is logged for visibility.

## Why this is low-risk (blast radius = VLAN 20 only)

- **BMC management is unaffected.** Ares reaches the BMCs over **L2 on the same subnet**
  (`.20.100 -> .20.x`); that traffic never traverses the firewall, so no L3 rule change
  can break it.
- No other interface's rules change; `filter reload` regenerates pf identically elsewhere
  and preserves established states.
- Worst case (a BMC loses NTP/DNS/phone-home) is non-critical and **observable** in the
  new block log, with instant rollback.

## Apply (on go)

```bash
~/Home-Lab/scripts/opnsense/vlan20-egress-clamp.sh            # dry-run (prints plan)
~/Home-Lab/scripts/opnsense/vlan20-egress-clamp.sh --apply    # execute
```
Mechanism: Ares -> ssh pve2 -> `qm guest exec 100` -> `php write_config` + `configctl
filter reload`. Backs up `/conf/config.xml` on the box first (path printed on apply).

## Verify (immediately after apply)

1. **BMC still reachable from Ares** (should be, it's L2): `ping 192.168.20.22`,
   open an iDRAC. (Ares needs its `enp0s31f6.20` leg up — see the Ares mgmt-path note.)
2. **BMC egress blocked:** from a BMC (or infer from the log) confirm it cannot reach
   VLAN 1 / internet. Watch the drops:
   `ssh root@192.168.10.204 "qm guest exec 100 -- tail -n 40 /var/log/filter/latest.log"`
   (or Firewall > Log Files > Live View, filter interface = TRUSTED).
3. **Observe ~10-15 min.** If a BMC is dropped reaching a *legitimate* service (NTP or
   DNS for time sync), add a narrow pass ABOVE the block: e.g. opt1 -> 192.168.20.1
   udp/123 (OPNsense serves NTP) and/or opt1 -> {Pi_holes} 53. Then `filter reload`.
4. **Rest of estate unaffected:** cluster quorate, DNS answering, fronts serving
   (they are on VLAN 1/30, whose rules did not change).

## Rollback (anytime)

```bash
~/Home-Lab/scripts/opnsense/vlan20-egress-rollback.sh /conf/config.xml.bak-vlan20clamp-<stamp>
```
Restores the pre-change config and reloads. opt1 returns to the original 4 rules.

## Open question for go/no-go

Do the BMCs need outbound NTP/DNS? Unknown without checking each BMC's config. The plan
handles this by **clamp-then-observe**: apply with logging, watch what the BMCs actually
try, and add narrow pinned allows only if something legitimate is dropped. No need to
answer before applying.
