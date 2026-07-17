# Runbook: VLAN 20 (BMC) Egress Clamp — Segmentation Phase 1.5

**Status: READY — awaiting go/no-go (2026-07-17).** Both pre-flight blockers cleared:
the floating-rule defect is fixed in the scripts (validated), and the guest agent was
revived (`qm agent 100 ping` responds). Final validations done: corrected PHP `php -l`
clean; `configctl filter reload` = `rc.filter_configure` confirmed; report-only dry-run
confirms it removes 3 interface passes, prepends 1 floating block, appends 1 interface
block, and leaves the failover rule's interface list untouched. Details below.
**Source:** AAR-2026-07-16 recommendation; the un-done half of `Security-VLAN-Segmentation-Phased-2026-07-03.md`.

## Pre-flight findings (2026-07-17) — adversarial failure-mode review

**PASSED (verified against live state):**
- BMC management is L2-safe: Ares reaches every BMC on-link via `enp0s31f6.20` (no
  firewall hop); confirmed `ip route get` = `dev enp0s31f6.20`, BMC .22 pingable.
- No live VLAN 20 egress dependency: 0 BMC through-firewall states; the one .20.100
  state was a STALE Discord connection (Discord is actually bound to Ares' .10.199).
- Ares has no internet fallback via .20.100: both default routes go via .10.1 (wired +
  WiFi), none via .20.1 — so the clamp can't break Ares internet even on a leg failover.
- Blast radius contained: dry-run selects exactly the 3 opt1 pass rules, 0 of 17
  other-interface rules.

**BLOCKER 1 (design defect — FIXED in the scripts):** a **quick** floating rule
`Mulit-WAN failover: internet-bound via Failover group` (`<quick>1</quick>`, interfaces
include opt1) passes VLAN 20 → internet BEFORE any interface rule is evaluated. The
original clamp (remove interface pass + default-deny) would therefore have left BMC
internet egress WIDE OPEN — failing its primary goal. **Fix:** the apply now PREPENDS a
dedicated **floating quick block** for opt1 internet-bound (dest !Local_Nets) that
precedes the failover rule; it does NOT edit the shared failover rule (that rule serves
6 other interfaces and is part of the in-progress WAN-failover work).

**BLOCKER 2 (mechanism — MUST CLEAR before apply):** the OPNsense qemu guest agent —
which BOTH the apply and the rollback drive — **went unresponsive mid-review** (`qm agent
100 ping` = "not running", though `agent: enabled=1`). OPNsense itself is fully healthy
(gateway/internet/DNS/API/fronts/BMC all green — only the management channel is down).
A firewall change whose rollback path is unavailable must not proceed. The apply/rollback
scripts now GATE on `qm agent 100 ping` and abort if it is down. **Revive the agent first**
(serial console `qm terminal 100` from pve2, or GUI: restart the os-qemu-guest-agent
service / `service qemu-guest-agent restart`). This also matters independently: with the
agent down, OPNsense will NOT shut down gracefully on a pve2 reboot (config-corruption risk).

**Residual to re-validate once the agent is back (before apply):** `php -l` lint of the
corrected apply PHP, and a report-only dry-run confirming it prepends 1 floating block,
removes 3 interface passes, adds 1 interface block, and leaves the failover rule untouched.

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
