# OPNsense CARP HA Pair — Build Plan (2026-07-22)

Removes the **top-ranked SPOF**: OPNsense is one VM (100) on one host (pve2). The
2026-07-20 DHCP outage ([[AAR-2026-07-20-DHCP-Kea-Outage]]) and the 2026-06-14 pve2
network incident both show the blast radius of that single box. This builds a second
OPNsense on a new Proxmox host as a **CARP high-availability pair** — automatic failover
of the gateway, firewall, and DHCP with no manual intervention.

Related: [[DNS-HA-OPNsense-Resilience-2026-07-10]] (DNS already HA), [[WAN-Failover-FirstNet-MR7400-Plan-2026-07-12]]
(WAN SPOF — do NOT conflate; that's upstream, this is the router node), [[DHCP-Kea-Monitoring-2026-07-21]].

## Version decision (see 2026-07-22 research)

- **Both nodes on OPNsense 25.7** — mature (25.7.11), ships **Kea v3** (steadier than the
  25.1 Kea we just crash-diagnosed), and **ISC still present as a fallback**. Clean single
  major step from the current **25.1.12**.
- **Hold on 26.1** (removes ISC → Kea-only, no safety net) until Kea is proven in HA here.
- **Match versions EXACTLY on both nodes.** Upgrade order forever after: **backup first →
  load-test → master**; never both at once; never skip two majors.

## Target topology

```
            CARP VIPs (float between nodes — clients never change)
  LAN gw .1  ·  TRUSTED .20.1  ·  SERVERS .30.1  ·  IoT .40.1  ·  VoIP .50.1  ·  GUEST .60.1  ·  LAB .70.1
        │
   ┌────┴─────────────┐              ┌──────────────────┐
   │ OPNsense MASTER  │══ pfsync ════│ OPNsense BACKUP  │   (dedicated sync link — NOT the LAN)
   │ VM 100 on pve2   │  (state)     │ VM on <new host> │
   │ real LAN .10.2   │              │ real LAN .10.3   │
   └──────────────────┘              └──────────────────┘
```

**Key renumber:** today OPNsense's *real* LAN IP **is** `.1`. Under CARP, `.1` becomes the
**VIP**; each node gets its own real IP (`.10.2` master / `.10.3` backup). Clients, DHCP
`routers` option, and DNS all keep pointing at `.1` (the VIP) — **no client-side change.**
Same pattern per VLAN (`.X.1` = VIP, `.X.2/.X.3` = real).

## Phase 0 — Decisions (before touching anything)

- [ ] **Backup host** confirmed. **NIC spec (derived from pve2's live layout 2026-07-22):**
      pve2 = 3 NICs, all assigned — `nic0`(onboard,100M)→vmbr0=**WAN**, `nic1`(1G)→vmbr1=**LAN
      trunk 1-70**, `nic2`(down)→vmbr2=**WAN2** (5G, planned). Each HA node needs, at minimum:
      **(1) WAN** → UDR (needs a free UDR LAN port for node 2), **(2) LAN trunk 1-70 @ 1GbE**
      (VLAN-aware — the one that matters), **(3) dedicated pfsync/HA-sync @ 1GbE** (direct
      cable between the two hosts is cleanest), optional **(4) WAN2** if you want 5G failover
      on the backup too. **→ Buy a 4× Intel GbE box** (firewall mini-PC or SFF + quad-port
      i350); **3 ports is the floor** if WAN2 is deferred. Hardware need NOT match pve2 — CARP
      needs equivalent interfaces + the same OPNsense version, and OPNsense is light (2c/4G).
- [ ] **⚠️ pfsync needs a port on pve2 too** — its 3 NICs are all used. Either repurpose the
      idle `nic2` (WAN2 spare) as pfsync now (free, but then the **5G WAN-failover project and
      CARP HA contend for `nic2`** — add a 4th NIC to pve2 to run both), or add a NIC to pve2.
      Decide which project owns `nic2`.
- [ ] **Cluster vs standalone:** run the backup OPNsense host **standalone** (like pve1), NOT
      in km-cluster — the gateway pair should not depend on cluster quorum health.
- [ ] **pfsync/sync link**: dedicated physical NIC between the two hosts (preferred) or a
      dedicated isolated VLAN. **Never run pfsync over the production LAN.**
- [ ] **IP renumber plan** locked: real IPs off every `.X.1`, VIPs claim `.X.1`.
- [ ] **WAN CARP approach** — the hard one. WAN is DHCP from the UpstreamUDR (`192.168.1.x`).
      CARP on WAN needs either multiple upstream IPs or a WAN CARP VIP the UDR routes to;
      with a single DHCP WAN this needs design + a lab test. Options to evaluate: WAN CARP
      VIP with a static upstream reservation, or keep WAN per-node and let CARP cover LAN
      only (internet still fails over because the backup's own WAN takes over routing).
- [ ] Version = **25.7** on both.

## Phase 1 — Build the backup node (no production impact)

- [ ] Install Proxmox on the backup host; replicate pve2's bridges (`vmbr0`=WAN/nic0,
      `vmbr1`=LAN/nic1 trunk, sync bridge). **`ifreload -a` does not apply bridge-vlan-aware
      changes — plan a reboot** (same pve2 caveat).
- [ ] Create the backup OPNsense VM: same vNIC layout as VM 100 (WAN, LAN + VLAN tags),
      **`agent: enabled=1` + a serial console from the start** (both June-14 "no console"
      and this session's "guest agent stopped" bit us — never ship an OPNsense VM without both).
- [ ] Install **OPNsense 25.7**; assign unique real IPs; set the box's `/etc/hosts`
      hostname→IP correctly from day one (avoid the pve2 `.members` `.200` drift).

## Phase 2 — Renumber the MASTER for CARP (maintenance window, console ready)

> Disruptive step — clients briefly lose the gateway while `.1` moves from real IP to VIP.
> Do it in a window with `qm terminal 100` open on pve2 as the escape hatch.

- [ ] On pve2 OPNsense: change each interface's real IP off `.X.1` (LAN → `.10.2`, etc.).
- [ ] Create a **CARP VIP** on each interface at `.X.1` (LAN `.1`, and every VLAN).
- [ ] Leave DHCP `routers` and DNS records pointing at `.X.1` (now the VIP) — unchanged.
- [ ] Verify clients still reach `.1` and the internet before proceeding.

## Phase 3 — Configure HA + DHCP failover

- [ ] **System → High Availability → Settings**: peer = backup's sync IP; enable **config
      sync (XMLRPC)** for rules, NAT, aliases, VIPs, **Kea DHCP**, Unbound, certs.
- [ ] **pfsync** on the dedicated sync interface (firewall-state sync).
- [ ] **CARP VIPs** present on all interfaces; advskew higher on the backup.
- [ ] **Kea DHCP HA hook** between the two nodes (hot-standby) so leases + the **12
      reservations** replicate and the backup serves DHCP on failover. (This is the
      direct fix for the class of outage that started all this.)
- [ ] Pi-holes (`.177`/`.178`) are separate and already HA — no change; they still get
      handed out by whichever OPNsense holds the VIP.
- [ ] Extend the age-encrypted **config backup** to cover the backup node too (or rely on
      HA sync + the single backup; document which).

## Phase 4 — Test before trusting (DHCP is foundational)

- [ ] **Config sync**: change a firewall rule on master → confirm it appears on backup.
- [ ] **Failover**: master → *Enter persistent CARP maintenance mode* (or stop VM 100) →
      confirm backup claims all VIPs, `.1` still routes, **DHCP still leases**, internet up,
      no client disruption.
- [ ] **Kea HA**: confirm leases + all 12 reservations are present/served on the backup
      during failover.
- [ ] **Failback**: exit maintenance / restart master → it reclaims MASTER cleanly, backup
      returns to standby.
- [ ] **Load test** under real traffic before relying on it.
- [ ] Point the **Kea health monitor** ([[DHCP-Kea-Monitoring-2026-07-21]]) at **both**
      nodes once HA is live.

## Gotchas (folded in from real incidents)

- Serial console + guest agent on **both** VMs, always (June-14; 2026-07-20 guest-agent stop).
- pfsync on a **dedicated** link, never the LAN.
- The real-IP renumber is the one risky step — console-ready, windowed.
- Same version both nodes; backup-first upgrades.
- Watch CARP config-sync/failback quirks (OPNsense HA forum) — validate, don't assume.
- Don't repeat the pve2 `/etc/hosts` `.200` drift on the new host.

## References

- OPNsense CARP HA + Kea HA docs; forum HA board.
- [[AAR-2026-07-20-DHCP-Kea-Outage]] · [[DNS-HA-OPNsense-Resilience-2026-07-10]] · [[DHCP-Kea-Monitoring-2026-07-21]]
