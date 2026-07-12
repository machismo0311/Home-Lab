# 🛡️ Runbook - Phased Security VLAN Segmentation (OOB · Services · Mgmt-Plane)
**Tags:** #runbook #network #vlan #security #proxmox #corosync #idrac #changerecord
**Related:** [[Runbook/VLAN30-Migration-Report-2026-07-02]] · [[Runbook/Node-VLAN-Migration-Template]] · [[Runbook/QuarkyLab-VLAN30-Server-Migration-2026-07-02]] · [[Networking/Network Overview]] · [[Infrastructure/Proxmox Cluster]] · [[00 - Homelab MOC]]

> **This runbook builds directly on the proven servers→VLAN 30 migration.** Read the two source docs on GitHub first - they are the authoritative pattern this plan reuses (dual-home, `commit confirmed`, add-before-remove, per-node lifelines):
> - **Report:** `machismo0311/Home-Lab` → `vault/Runbook/VLAN30-Migration-Report-2026-07-02.md`
> - **Template:** `machismo0311/Home-Lab` → `vault/Runbook/Node-VLAN-Migration-Template.md`

| | |
|---|---|
| **Change ID** | NET-2026-07-03-SEG (planned) |
| **Author / operator** | K. Mason (with Claude Code) |
| **Change type** | Network segmentation + credential rotation - additive-first, reversible |
| **Systems** | EX3400; OPNsense; 3× BMC (iDRAC/IPMI); pve3 service LXCs; QuarkyLab (Wazuh) |
| **Golden rule** | **Never move Corosync across a routed VLAN.** The cluster ring stays on VLAN 1 L2, exactly as in the VLAN 30 migration. |

---

## 📊 Phase tracker (fill in as each phase is executed + verified)

> Update the row **only after** the phase's verification step passes. Set status ✅, stamp the date, and record the concrete evidence (the command output / dashboard code that proved it). Mirror any change into `Vaults/homelab-vault/` and re-push the submodule.

| Phase | Scope | Status | Date done | Verified by (evidence) |
|---|---|---|---|---|
| **1** | BMCs → VLAN 20 + credential rotation | ✅ **Done & verified** | 2026-07-03 | **All 3 BMCs on VLAN 20** (iDRAC `.20.20`/`.20.21`, IPMI `.20.22`); creds rotated → Vaultwarden; native VLAN 1 dropped (1.4); Ares `.20` leg persisted; docs synced. **1.5 firewall verified**: Ares→BMC pass (HTTPS 302/302/200), pve3 (VLAN 1) + Randy (VLAN 30) → BMC **blocked**; BMC egress default-denied. ⚠️ Ares wired `enp0s31f6` flapped 3× (hardware - see log). |
| **2** | Service LXCs → VLAN 30 (dual-home NPM; +Open WebUI) | ✅ **Done (scoped)** 2026-07-08 | 2026-07-08 | **Final disposition:** NPM dual-homed; **Vaultwarden `.30.182`** + **Open WebUI `.30.185`** isolated to VLAN 30 (the high-value exposed apps). **Homepage CT106 + Grafana CT103 DECIDED to STAY on VLAN 1** (2026-07-08) - coupling recon showed they're mgmt/observability tools reaching the whole mgmt plane (Homepage→Proxmox `:8006`×4/PBS/switches/UniFi/OPNsense; Grafana→node_exporter `:9100`); moving them would re-open VLAN30→VLAN1 mgmt holes = isolation theater. Their exposure stays mitigated at NPM (auth + `:3000` firewalled-to-NPM). Wazuh/Headscale/Pi-hole stay VLAN 1 (as planned). Homepage Vaultwarden tile repointed to public URL (was direct `.10.182`). DNS foundation (OPNsense allow + Pi-hole permit-all-origins) done. Recon+plan detail below. **Step 0 ✅ (2026-07-08):** operator tagged VLAN 30 on pve3's UniFi port; verified - pve3 temp `vmbr0.30` reached `.30.1` (OPNsense) + `.30.187` (Randy), 0% loss, then cleaned up. UniFi controller = **192.168.10.2** (not `.1.1`=OPNsense). `nic0` uplink already trunks VID 2-4094; bridge self only had VID 1 (why first host-test false-negatived). **Step 1 ✅ (2026-07-08):** NPM dual-homed - CT101 `net1` eth1=`192.168.30.181/24` (no gw, persisted in config); ingress unchanged (vault 200/grafana 302/homepage 401/chat 200), `:81` admin 200, default route still eth0/`.10.1`, reachable from Randy. Snapshot `pre-vlan30`. (Pre-existing: `llm.netframe.local`→502, Jarvis llm_router down, unrelated.) **Step 2 ✅ Vaultwarden pilot (2026-07-08):** CT102 → VLAN30-only `.30.182` gw `.30.1` (add-before-remove, **zero vault downtime**, snapshot `pre-vlan30`); NPM upstream repointed `.10.182→.30.182` - edited conf `proxy_host/1.conf` `set $server` + `nginx -t` + graceful `nginx -s reload`, **and** persisted in NPM `database.sqlite` `proxy_host.forward_host` (via python3). vault 200 throughout, `.10.182` gone. **DNS ✅ resolved (2026-07-08) - TWO parts:** (1) OPNsense **Servers→`192.168.10.177:53` Pass (TCP/UDP)**, placed above the interface block rules; (2) **Pi-hole Settings→DNS→Interface = "Permit all origins"** (was "Allow only local requests", which silently dropped/RST'd VLAN30-source queries - TCP `:53` connected but query reset; UDP timed out). Safe: Pi-hole has no WAN port-forward, OPNsense gates who reaches `:53`. This unblocks DNS for ALL VLAN30-only CTs. Diag: `1.1.1.1` answered but `.177` didn't → not the firewall. Gotcha: `pct set --delete net0` on a running CT removed eth0 live but LEFT the config line → remove with `sed -i '/^net0:/d' /etc/pve/lxc/<id>.conf`. gw persistence: direct-edit conf (append `,gw=...` to net1) to avoid hot re-init. **Step 3 ✅ Open WebUI CT107 (2026-07-08):** VLAN30-only `.30.185` gw `.30.1`, off `.10.185`; NPM chat upstream `6.conf` + DB → `.30.185:8080`; chat 200 throughout; DNS/egress OK (Pi-hole foundation seamless). ✅ **llm loose ends resolved (2026-07-08):** llm_router.service on Jarvis had been **manually stopped** (clean TERM 11:08) → restarted, binds `0.0.0.0:8000`, reachable on VLAN30 `.30.31:8000`=200. Open WebUI `OPENAI_API_BASE_URL` repointed `.10.31→.30.31` (systemd, restart; chat 200 after ~15s startup) - backend now works over VLAN30, no firewall hole. `llm.netframe.local/v1/models`=200. pre-vlan30 snapshots (CT101/102/107) deleted. Next: **Grafana CT103** + **Homepage CT106** - both complex (bidirectional monitoring / widget couplings), map fully before moving. |
| **3** | VLAN 1 mgmt-plane firewall clamp (OPNsense) | ✅ **Done & verified** 2026-07-10 | 2026-07-10 | **Recon via read-only OPNsense API** (pulled live `config.xml` through the backup key at `~/.config/opnsense-backup/api.env` → `/api/core/backup/download/this`): **all 6 VLANs 20/30/40/50/60/70 are assigned/routed** (opt1–opt6). Critical finding - **every non-mgmt segment was ALREADY clamped**: IoT(40)/Guest(60)/Lab(70)/VoIP(50) each carry `block → Local_Nets`; VLAN 20 (TRUSTED) is deliberately `pass → mgmt`+`pass → servers` (Ares admin path); **the ONLY gap was SERVERS/VLAN 30** (`pass → any` reached VLAN 1). 3.1 Ares VLAN 20 leg already satisfied (Phase 1). **Action = ONE rule** on Servers(VLAN 30): `Block SERVERS net → 192.168.10.0/24`, ordered **below** the `.177:53` DNS pass + `.20.0/24` BMC block, **above** `Allow servers internet`. Used surgical `/24` **NOT** `Local_Nets` - config showed **VoIP→FreePBX lives on VLAN 30** (`Allow VoIP → 192.168.30.0/24`), so a blanket local block would break FreePBX↔phones. **Verified both ways (2026-07-10):** (a) API config re-pull confirms rule order `1 DNS / 2 BMC-block / 3 VLAN1-block / 4 internet`; (b) live from Vaultwarden CT102 (.30.182): pve3 `:8006` → `000` **blocked**, Pi-hole admin `:80` → `000` **blocked**, DNS resolves github.com, internet egress OK; ingress `vault`=200 / `chat`=200 unaffected. **This retroactively makes Phase 2's isolation real** (moved CTs can no longer touch the mgmt plane). OPNsense field gotcha: enter dest as `192.168.10.0` + CIDR dropdown `24`, not the `/24` string. Optional deferred (gold-plating, not required): limit VLAN 1→internet egress; tighten VLAN 20→mgmt to specific ports. |

**Status legend:** ⬜ Not started · 🟡 In progress · ✅ Done & verified · ↩️ Rolled back

**Sub-step ledger** (optional finer granularity - tick as completed):
- Phase 1: ☑ 1.0 pre-flight ☑ 1.1 switch trunk ☑ 1.2 BMC VLAN 20 IP ☑ 1.3 cred rotation ☑ 1.4 drop VLAN 1 ☑ 1.5 firewall ☑ docs updated ☑ Ares `.20` leg persisted - **PHASE 1 COMPLETE**
- Phase 2: ☑ NPM (dual-homed) ☑ Vaultwarden→.30.182 ☑ Open WebUI→.30.185 ☑ DNS foundation ✅ **Grafana/Homepage = KEEP on VLAN 1 (decided 2026-07-08, mgmt tools)** ☑ couplings swept - **PHASE 2 COMPLETE (scoped)**
- Phase 3: ☑ Ares VLAN 20 leg (Phase 1) ☑ firewall matrix applied (one VLAN30→VLAN1 block; 40/50/60/70 already clamped) ☑ negative-test from untrusted host (VLAN30 CT: :8006/:80 blocked, DNS+egress+ingress OK) ☑ VLAN 30 report Phase-3 residual closed - **PHASE 3 COMPLETE ✅ (2026-07-10). ALL THREE PHASES DONE.**

### Execution log - Phase 1 (2026-07-03)
- **Pre-flight ✅** - BMCs `.20/.21/.22` reachable; Tailscale lifelines up; Ares wired `enp0s31f6 .100` restored (was `linkdown` - see topology note).
- **⚠️ Topology correction:** `CLAUDE.md` states Ares WiFi is WAN-side (`192.168.1.x`); observed 2026-07-03 it is on **VLAN 1** (`wlp2s0 192.168.10.199`) and the wired leg had been down. Wired leg now up (BMC/switch traffic prefers `enp0s31f6`), WiFi is backup. **TODO:** correct `CLAUDE.md` + [[Networking/Network Overview]].
- **BMC MACs (for switch-port mapping):** QuarkyLab iDRAC `.20` = `XX:XX:XX:XX:XX:XX` · Jarvis iDRAC `.21` = `XX:XX:XX:XX:XX:XX` · Randy IPMI `.22` = `XX:XX:XX:XX:XX:XX`. (EX3400 MAC-table lookup pending switch login - key auth denied.)
- **Switch ports (from EX3400 MAC table):** QuarkyLab iDRAC `.20` → **ge-0/0/30** · Jarvis iDRAC `.21` → **ge-0/0/44** · Randy IPMI `.22` → **ge-0/0/32** · Ares → **ge-0/0/41**. Each BMC port had exactly 1 learned MAC (direct access). ⚠️ old buildout doc's "ge-0/0/32 = UniFi uplink" is **stale** - live UniFi trunk is ge-0/0/46.
- **1.1 Switch trunk ✅ committed (2026-07-03):** ge-0/0/30·32·41·44 → `interface-mode trunk`, `native-vlan-id 1`, `vlan members [default trusted]`. Applied via `commit confirmed 10`, verified BMCs still ping on `.10.x` (native VLAN 1 intact) + switch/Ares links up, then plain `commit`. `show vlans trusted` = 30/32/41/44/46.
- **1.2 Ares VLAN 20 leg ✅ (2026-07-03, live/non-persistent):** created `enp0s31f6.20` = `192.168.20.199/24` (VLAN 20 tagged). Switch learns Ares MAC on `trusted` (ge-0/0/41). Direct VLAN 20 **L2 confirmed** - ARP resolves `.20.1` → OPNsense `XX:XX:XX:XX:XX:XX` over `enp0s31f6.20`. ICMP to `.20.1` is dropped by OPNsense's VLAN 20 interface firewall (no allow rule yet - Phase 3); irrelevant to same-subnet Ares↔BMC. ⚠️ one transient wired-carrier drop mid-session (cable reseated → stable). **Not yet persisted** to `/etc/network/interfaces` (deliberate - persist after BMCs verified).
- **Fallback for BMC re-IP:** if a BMC becomes unreachable on VLAN 20, recover via **Tailscale → node → Redfish** (iDRACs) / `ipmitool` (Randy). Do BMCs **one at a time**, QuarkyLab iDRAC as pilot.
- **1.3 QuarkyLab iDRAC ✅ (pilot, 2026-07-03):** re-IP'd `.10.20 → 192.168.20.20` (VLAN 20 tagged, gw `.20.1`) via iDRAC web UI; root password rotated same visit → Vaultwarden. Verified from Ares: `.20.20` direct via `enp0s31f6.20` (3/3), `.10.20` gone, HTTPS 302, switch learns iDRAC MAC on `trusted` (ge-0/0/30). Stale `default`-VLAN MAC entry aging out (no VLAN 1 IP).
- **1.3 Jarvis iDRAC ✅ (2026-07-03):** re-IP'd `.10.21 → 192.168.20.21` + root pw rotated (web UI). Verified from Ares: `.20.21` direct (3/3), `.10.21` gone, HTTPS 302, MAC on `trusted` (ge-0/0/44).
- **1.3 Randy IPMI ✅ (2026-07-03):** scripted in-band via `ipmitool` on the Randy host (channel 1): set ipaddr/netmask/defgw, then `vlan id 20`. **Gotcha:** enabling the VLAN zeroed the IP (`0.0.0.0`) - re-applied ipaddr/netmask (no lockout, in-band). ADMIN pw rotated (web UI, user id 2). Verified from Ares: `.20.22` direct (4/4), `.10.22` gone, HTTPS 200, MAC on `trusted` (ge-0/0/32).
- **1.4 Drop native VLAN 1 ✅ (2026-07-03):** ge-0/0/30·32·44 → `vlan members trusted` only, `native-vlan-id` removed (stale `default` MACs had already aged out - BMCs send tagged-20 exclusively). `commit confirmed 5`, verified all 3 BMCs still up on `.20.x` + gone from `.10.x`, then `commit`. Ares ge-0/0/41 left dual (native 1 + tagged 20).
- **Ares `.20` leg persisted ✅:** `enp0s31f6.20` = `192.168.20.199/24` (no gateway) added to `/etc/network/interfaces` (backup `interfaces.bak-vlan20-*`); `ifquery` validates; live iface not reloaded.
- **Docs synced ✅:** CLAUDE.md + [[Networking/Network Overview]] BMC IPs → `.20.x`; Ares WiFi-on-VLAN1 correction recorded.
- **1.5 OPNsense firewall ✅ verified (2026-07-03):** operator added **Block** rules on **LAN** and **Servers (VLAN 30)** interfaces (`<iface> net → 192.168.20.0/24`, above the allow-any), plus a **Pass** `192.168.10.199 (Ares) → 192.168.20.0/24` for WiFi-path resilience. BMC egress was already default-denied by the VLAN 20 interface (no pass rules). Verified: Ares→BMC **pass** (ping + HTTPS 302/302/200 over L2 `enp0s31f6.20`), pve3 (VLAN 1) **blocked**, Randy (VLAN 30) **blocked**. Key insight: Ares↔BMC is same-subnet **L2 and bypasses OPNsense**, so no allow was strictly required for the wired path - the Pass rule only matters when Ares falls back to WiFi.
- **⚠️ OUTSTANDING HARDWARE ISSUE:** Ares wired leg `enp0s31f6` (switch `ge-0/0/41`) **flapped 3× during this session** - carrier drops to 0; admin `ip link set up` does not restore it when the cable is physically out. It is **both** the documented mgmt lifeline **and** the VLAN 20 jump-host L2 path. **Action: replace the patch cable / try another switch port.** When it's down, Ares silently reroutes VLAN 20 traffic via WiFi→OPNsense (correctly blocked by the firewall), so BMC access is lost until the Pass-Ares rule or the cable is in play. - **PHASE 1 COMPLETE (all sub-steps ✅).**

---

## 0. Objective & threat model

Today **VLAN 1 is flat**: hypervisor management + corosync, out-of-band BMCs (with default creds `root / factory-default (creds in Vaultwarden)` and `ADMIN`), internet-exposed web apps (Vaultwarden, Homepage, Grafana, NPM), and the admin workstation all share one broadcast domain. A single compromised web service sits at L2 next to the Proxmox `:8006` API and the iDRACs.

**Target state - three trust tiers, built in three phases:**

| Phase | Goal | Tier produced |
|---|---|---|
| **1** | Move BMCs off the flat LAN + rotate default creds | **VLAN 20** - out-of-band, reachable from Ares only, no egress |
| **2** | Move internet-exposed service containers off the mgmt plane | **VLAN 30** - server workloads (reuses the existing servers segment) |
| **3** | Firewall VLAN 1 down to a pure management plane | **VLAN 1** - hypervisor mgmt + corosync only, reachable from VLAN 20 only |

**Out of scope (deliberately):** moving corosync; moving pve host mgmt IPs off VLAN 1; moving Pi-hole (`.10.177`) - it stays as directly-connected DNS for all tiers via a firewall allow.

---

## Fill-in parameters (complete before starting)

| Param | Value |
|---|---|
| Admin workstation (jump host) | Ares - VLAN 1 `192.168.10.199` (wired `enp0s31f6`) |
| Trusted/OOB VLAN id / subnet / gw | `20` / `192.168.20.0/24` / `192.168.20.1` |
| Servers VLAN (existing) | `30` / `192.168.30.0/24` / `192.168.30.1` |
| QuarkyLab iDRAC - new IP | `192.168.20.20` (from `192.168.10.20`), svc tag (in ops vault) |
| Jarvis iDRAC - new IP | `192.168.20.21` (from `192.168.10.21`) |
| Randy IPMI - new IP | `192.168.20.22` (from `192.168.10.22`) |
| BMC switch ports (dedicated NICs) | `<discover via MAC table>` - see Phase 1 pre-flight |
| Service LXCs (pve3) | NPM 101 `.181`, Vaultwarden 102 `.182`, Grafana 103 `.183`, Homepage 106 `.148` |
| EX3400 admin | `mason@192.168.10.50` (password in **Vaultwarden**) |

---

# Phase 1 - Out-of-band lockdown (BMCs → VLAN 20) + credential rotation

**Why first:** highest security ROI. Full hardware/console control of all three servers is currently one flat hop away behind vendor-default passwords. BMCs are standalone (their own dedicated NICs) and belong to **no cluster** - moving them cannot touch corosync or quorum, so this phase is low-blast-radius despite being high-value.

### 1.0 Pre-flight (read-only gate)
```bash
# Confirm each BMC responds on VLAN 1 today
for i in 20 21 22; do ping -c1 -W1 192.168.10.$i && echo "  .$i UP"; done
# Discover each BMC's DEDICATED switch port by its MAC (run per BMC MAC)
ssh mason@192.168.10.50 'show ethernet-switching table | match <bmc-mac>'
# Secondary lifeline into each host (survives BMC re-IP): Tailscale on the node
for n in quarkylab randy jarvis; do ssh $n 'tailscale ip -4 | head -1'; done
```
**Gate:** all 3 BMCs ping, their switch ports identified, Tailscale up on all 3 hosts (so a locked-out BMC is still recoverable host-side). Confirm you have console/crash-cart access to at least one node.

### 1.1 Switch - trunk VLAN 20 to each BMC port (additive, `commit confirmed`)
First define VLAN 20 if it is access-facing only on the trunk today, then trunk each dedicated BMC port. Per the template, use the dead-man switch:
```
configure
set vlans trusted vlan-id 20                       # if not already present
set interfaces <bmc-port> unit 0 family ethernet-switching interface-mode trunk
set interfaces <bmc-port> unit 0 family ethernet-switching vlan members default
set interfaces <bmc-port> unit 0 family ethernet-switching vlan members trusted
set interfaces <bmc-port> native-vlan-id 1
show | compare
commit confirmed 5
```
**Verify within 5 min** from Ares: `ping 192.168.10.<i>` for each BMC still works (still answering untagged on native VLAN 1). **Good →** `commit`. **Bad →** auto-rollback in 5 min.

### 1.2 BMC - add VLAN 20 tagged IP (add-before-remove)
On each iDRAC/IPMI **web UI** (simplest; racadm is not installed and Ares curl can't negotiate the iDRAC's legacy TLS - see [[Compute/Dell R730 - ML Node]]). If you must script it, use **Redfish curl FROM the node** as documented.

- iDRAC → **iDRAC Settings → Network**: set **VLAN Enable = On, VLAN ID = 20**, static `192.168.20.<i>/24`, gateway `192.168.20.1`.
- The BMC will drop off `192.168.10.<i>` and reappear on `192.168.20.<i>` (tagged). This brief loss is harmless - no workload rides a BMC.

**Verify from Ares once Ares can reach VLAN 20** (Ares gets a VLAN 20 leg in Phase 3, or temporarily trunk VLAN 20 to Ares' port now):
```bash
for i in 20 21 22; do ping -c1 -W1 192.168.20.$i && echo "  .$i on VLAN 20 UP"; done
```

### 1.3 Rotate BMC credentials (do NOT skip - segmentation ≠ auth)
While in each BMC UI: replace `root / factory-default (creds in Vaultwarden)` (iDRACs) and `ADMIN` (Randy IPMI) with strong unique passwords. **Store in Vaultwarden**, never in this (public) repo. Reference only, per C7 of the VLAN 30 report.

### 1.4 Remove VLAN 1 footprint (optional hardening, after VLAN 20 verified)
Once every BMC is confirmed on VLAN 20 and reachable from Ares, drop native VLAN 1 from the BMC ports so the BMCs have **no** VLAN 1 presence:
```
set interfaces <bmc-port> unit 0 family ethernet-switching vlan members trusted
delete interfaces <bmc-port> unit 0 family ethernet-switching vlan members default
# convert to access if desired:  set ... interface-mode access
commit confirmed 5   # verify VLAN 20 reachability, then commit
```

### 1.5 Firewall (OPNsense) - see Phase 3 matrix
Add now: **allow Ares → VLAN 20** (BMC mgmt ports 443/623/5900), **deny all other → VLAN 20**, **deny VLAN 20 → any** (no egress - BMCs never need the internet).

> ⚠️ **Update docs after Phase 1:** the VLAN 30 report lists iDRAC/IPMI on `.10.20/.21/.22` as a *lifeline*. After this phase that lifeline is on VLAN 20; update `CLAUDE.md`, [[Networking/Network Overview]], and the node compute docs. Tailscale remains the re-IP-proof lifeline.

---

# Phase 2 - Service LXCs → VLAN 30 (reuse the servers segment)

> ### 🔄 EXECUTION PLAN - revised & reconciled 2026-07-08 (read this first)
> A live survey reconciled the 5-day-old plan below. Key deltas + decisions:
> - **pve3 is behind the UniFi switch** (its MAC is on EX3400 `ge-0/0/46`, the UniFi trunk). So VLAN 30 → pve3 is a **UniFi access-port** change (native VLAN 1 + tagged VLAN 30), **not** an EX3400 change. VLAN 30 already transits `ge-0/0/46`. **Operator applies it in UniFi; verify before any container moves.**
> - **`vmbr0` is VLAN-aware** on pve3 → per-container `pct set --net0 ...,tag=30` works (no sub-interface needed).
> - The four movers are **DHCP-reserved** (OPNsense, by MAC) → convert to **static** on VLAN 30 to avoid a VLAN 30 DHCP dependency.
> - **NPM: dual-home, do NOT re-IP** (decision 2026-07-08). Add a VLAN 30 vNIC (`.30.181`), keep the VLAN 1 leg (`.181`) for WAN ingress + `:81` admin. No OPNsense WAN-forward or admin-allowlist changes; NPM reaches moved backends on VLAN 30 and still reaches Wazuh/llm on VLAN 1.
> - **Open WebUI CT 107 (`.185`) INCLUDED** (new service since original plan) → `.30.185`.
>
> **NPM coupling map** (CT 101 Docker `jc21/nginx-proxy-manager`; `set $server` in `/opt/nginx-proxy-manager/data/nginx/proxy_host/*.conf`):
> | Public name | Upstream now | Backend | Action |
> |---|---|---|---|
> | vault.kylemason.org | `.10.182` | Vaultwarden CT102 | → `.30.182` |
> | grafana.kylemason.org | `.10.183` | Grafana CT103 | → `.30.183` (+ VLAN30→VLAN1 `:9100` allow for Prom scrape) |
> | homepage.kylemason.org | `.10.148` | Homepage CT106 | → `.30.148` |
> | chat.netframe.local | `.10.185` | Open WebUI CT107 | → `.30.185` |
> | llm.netframe.local | `.10.31` | llm_router (Jarvis) | stay (optional repoint → `.30.31`) |
> | wazuh.kylemason.org | `.10.184` | Wazuh (QuarkyLab VM104) | stay VLAN 1 |
>
> **Sequence - one at a time; `vzdump` snapshot + verify + git checkpoint between each:**
> 0. **Operator (UniFi):** trunk VLAN 30 → pve3 port (native 1 + tagged 30). **Verify:** temp `vmbr0.30` on pve3 (`192.168.30.250/24`) pings `.30.1`, then remove it.
> 1. **Dual-home NPM** - add `net1` `tag=30` `.30.181` to CT 101; verify WAN ingress + `:81` admin still work.
> 2. **Pilot: Vaultwarden CT102** → `.30.182`; repoint NPM `$server`; verify `vault.kylemason.org` end-to-end.
> 3. **Homepage CT106** → `.30.148`; then **Grafana CT103** → `.30.183` (add `:9100` allow); then **Open WebUI CT107** → `.30.185`.
> - **Stay on VLAN 1:** Headscale CT105, Wazuh VM104, Pi-hole (DNS reachable cross-VLAN by firewall allow).

**Why:** isolate internet-exposed apps from the hypervisor management plane. This reuses the **exact dual-home mechanics** of the VLAN 30 migration - but here we tag a *container's* vNIC, not the host's. **The pve3 host mgmt IP stays on VLAN 1.**

### 2.0 Per-service disposition (decide before moving)

| Service | LXC/VM | Now | Action | Rationale |
|---|---|---|---|---|
| NPM (ingress) | 101 / pve3 | `.10.181` | **Move → `.30.181`** | Sole WAN ingress; belongs in the workload/DMZ tier |
| Vaultwarden | 102 / pve3 | `.10.182` | **Move → `.30.182`** | Internet-exposed web app |
| Grafana/Prom/Loki | 103 / pve3 | `.10.183` | **Move → `.30.183`** | Exposed UI; needs a firewall hole to scrape VLAN 1 `:9100` (see below) |
| Homepage | 106 / pve3 | `.10.148` | **Move → `.30.148`** | Internet-exposed dashboard |
| Wazuh | VM 104 / QuarkyLab | `.10.184` | **Keep on VLAN 1** | Agents on VLAN 1 nodes → manager; moving forces cross-VLAN agent traffic. Revisit later. |
| Headscale | 105 / pve3 | `.10.186` | **Keep on VLAN 1** | VPN control plane; re-IP disrupts all tailnet clients. Leave unless you re-key deliberately. |
| Pi-hole | pve1 LXC | `.10.177` | **Keep on VLAN 1** | Shared DNS for all tiers via firewall allow (per template Step 5) |

> The two exposed collectors (Grafana/Prometheus) do move, but they must still reach `node_exporter` on VLAN 1 hosts - that requires a **VLAN 30 → VLAN 1 `:9100`** allow (see Phase 3). This is an accepted, narrow hole; everything else VLAN 30 → VLAN 1 stays denied.

### 2.1 Per-container migration (repeat for NPM, Vaultwarden, Grafana, Homepage - **one at a time, verify between**)

Reserve the new IP, snapshot/back up the container to PBS first, then re-tag its vNIC to VLAN 30 and re-address inside:
```bash
# On pve3 - back up, then re-point the container NIC to VLAN 30 (vmbr0.30 tagged)
vzdump <CTID> --storage <pbs> --mode snapshot          # fresh restore point
pct set <CTID> --net0 name=eth0,bridge=vmbr0,tag=30,ip=192.168.30.<x>/24,gw=192.168.30.1
pct reboot <CTID>
```
> If `vmbr0` is **not** vlan-aware, use the `vmbr0.30` sub-interface pattern from the VLAN 30 report (C5). If you ever enable `vlan_filtering` on `vmbr0`, add VID 30 to the bridge/port PVID/vids - documented caveat.

**Verify (per container):**
```bash
pct exec <CTID> -- ip -br a                              # on 192.168.30.<x>
pct exec <CTID> -- sh -c 'ping -c2 192.168.30.1; getent hosts github.com'   # gw + DNS
```

### 2.2 Fix the couplings (add-before-remove; sweep for hardcoded `.10` IPs)
This is where the VLAN 30 report's C8 (hidden IP couplings) bites hardest. For **each** moved service, update every reference, then verify end-to-end:

- **NPM upstreams:** every proxy host pointing at `.10.182 / .10.183 / .10.148` → repoint to `.30.x`. If NPM itself moved to `.30.181`, update the WAN port-forward / firewall target on OPNsense.
- **DNS records** (Pi-hole local + any public A/CNAME behind Cloudflare/NPM) → new `.30.x`.
- **Homepage widgets** (`/opt/homepage/config`) referencing service IPs → `.30.x`.
- **Grafana datasources / Prometheus targets** → keep scraping VLAN 1 `:9100` (allowed hole); Grafana's own URL changes to `.30.183`.
- **NPM `:81` admin allowlist** (currently locked to Ares `.199`, DOCKER-USER F-05) → update to Ares' reachable IP.
```bash
ssh pve3 'grep -rIn "192.168.10.\(181\|182\|183\|148\)" /opt 2>/dev/null'   # sweep
```
Prove each service through its real front door (browser via NPM) before moving the next.

### 2.3 Rollback (per container)
`pct set <CTID> --net0 ...tag=<none>,ip=192.168.10.<orig>/24,gw=192.168.10.1` + `pct reboot`; revert NPM/DNS/Homepage refs; restore from the pre-move `vzdump` if needed.

---

# Phase 3 - VLAN 1 management-plane hardening (OPNsense firewall)

**Why last:** only after BMCs (Phase 1) and exposed services (Phase 2) have left VLAN 1 can you safely clamp it. This also completes the "Phase 3 (operator, OPNsense GUI)" item explicitly deferred at the end of the VLAN 30 report.

### 3.1 Give Ares a VLAN 20 (trusted) presence
Ares is the jump host - the only thing allowed into the management plane and the BMCs. Add a VLAN 20 leg (tagged sub-interface on `enp0s31f6`, or trunk its EX3400 port native 1 + tagged 20). Keep the wired VLAN 1 leg during cutover so you can't lock yourself out (WiFi is WAN-side `192.168.1.x`).

### 3.2 Inter-VLAN firewall matrix (target)

| Source → Dest | Allow | Notes |
|---|---|---|
| **VLAN 20 (Ares/OOB)** → VLAN 1 mgmt | ✅ | SSH `:22`, PVE `:8006`, PBS `:8007`, EX3400, iDRAC mgmt |
| **VLAN 20** → BMCs (VLAN 20) | ✅ | Ares only; 443/623/5900 |
| any → **VLAN 20** | ❌ | except Ares |
| **VLAN 20 (BMCs)** → any | ❌ | no BMC egress |
| any (except VLAN 20) → **VLAN 1 mgmt** | ❌ | management plane is closed |
| **VLAN 30 services** → VLAN 1 `:9100` | ✅ (narrow) | Grafana/Prometheus scrape only |
| **all tiers** → Pi-hole `.10.177:53` | ✅ | shared DNS (per template Step 5) |
| **VLAN 30** → internet (egress) | ✅ | via `.30.1` (already live) |
| **VLAN 1 mgmt** → internet | ⛔ / limited | allow only OS/PVE update endpoints if desired |
| Guest 60 / IoT 40 → any internal | ❌ | isolated (UniFi-side; verify) |

### 3.3 Verify the clamp (from a non-trusted host, expect failures)
```bash
# From a VLAN 30 service box - mgmt plane should be UNREACHABLE:
ssh vaultwarden 'curl -m3 -sk https://192.168.10.201:8006 && echo REACHABLE(bad) || echo blocked(good)'
# From Ares VLAN 20 - mgmt plane SHOULD work:
curl -m3 -sk https://192.168.10.201:8006 -o /dev/null -w "%{http_code}\n"     # expect 200/401
# DNS still resolves from every tier:
ssh vaultwarden 'getent hosts github.com'
```

---

## Global safeguards (carried from the VLAN 30 migration)
- **Corosync untouched** on VLAN 1 - the cluster is never at risk in any phase.
- **`commit confirmed 5`** on every EX3400 change (dead-man auto-rollback).
- **Additive-first / add-before-remove** at every step - fully reversible.
- **Two lifelines per host:** BMC (Phase-appropriate VLAN) **and** Tailscale (survives any re-IP).
- **One device/container at a time**, verifying before the next; VM-hosting node last.
- **Back up before you touch:** `vzdump` each LXC; `interfaces.bak-*` on any node edit; export switch config.
- **No secrets in this public repo** - EX3400/iDRAC/Grafana creds live in **Vaultwarden** (report C7).
- **Keep Ares wired on VLAN 1** through the whole change (WiFi is WAN-side; OPNsense is the inter-VLAN SPOF - report C3).

## Rollback (whole change, any phase)
1. **Phase 3:** disable the new VLAN 1 deny rules → back to permissive inter-VLAN.
2. **Phase 2:** revert each container to `.10.x` (untagged) + restore NPM/DNS refs (or `vzdump` restore).
3. **Phase 1:** BMC network config back to VLAN 1 `.10.<i>` untagged; switch `rollback 1; commit`. (Credential rotation is kept - it's pure upside.)
4. **Cluster:** nothing to undo - untouched throughout.
5. **Lockout recovery:** node console / crash-cart, or `ssh <tailscale-ip>` into the host, then fix the BMC/bridge from inside.

## Do / Don't
- ✅ Rotate the BMC default creds **regardless** of how far you take the VLAN work - that's the single biggest fix.
- ✅ Keep Pi-hole, Headscale, and corosync where they are; open narrow firewall holes instead of moving infra.
- ✅ Verify from a *non-trusted* host that the mgmt plane is actually unreachable - an untested firewall is a false sense of security.
- ❌ Don't move corosync or any pve host mgmt IP. ❌ Don't clamp VLAN 1 (Phase 3) before BMCs+services have left it. ❌ Don't drive a switch/BMC cutover over the exact path you're re-IP'ing without a second lifeline. ❌ Don't commit secrets to this public vault.

---

## DNS-gap fix for isolated VLANs (2026-07-11)
**Found during review:** IOT(40)/VoIP(50)/GUEST(60)/LAB(70) all `block → Local_Nets` (which includes VLAN 10 where Pi-hole `.177/.178` live), but DHCP hands those VLANs `.177/.178` as DNS → **those VLANs had no working DNS** (latent; sparsely populated). Their gateway Unbound (`.X.1`) is also inside `Local_Nets` so that was blocked too. TRUSTED/SERVERS were fine (explicit DNS allows).

**Fix:** added a narrow pinhole - host alias `Pi_holes = 192.168.10.177,192.168.10.178` + 4 **automation** filter rules (`Firewall → Automation → Filter`), one per VLAN: `pass in quick <VLAN net> → Pi_holes proto tcp/udp port 53`. Applied via the firewall API.

**Verified at pf level** (`/tmp/rules.debug`): the automation `pass` rules land at lines 228–231, *before* the manual `block → Local_Nets` at 243–250 - so `:53 → Pi-holes` passes (DNS works + keeps Pi-hole ad-blocking/HA) while all other local traffic still hits the block (isolation preserved). Key insight: **OPNsense automation-filter rules evaluate before per-interface manual rules.**

**Rollback:** delete the 4 automation rules + the `Pi_holes` alias (or restore the pre-change `config.xml` snapshot). Rules are additive `pass` - removing them only reverts to the prior (DNS-broken) state, breaks nothing else.

## Hardening: log denied traffic (2026-07-11)
**Gap:** none of the 8 manual `block` rules logged → lateral-movement / policy-violation attempts were invisible (no Wazuh/firewall-log signal). IPv6 checked - not configured on VLANs, default-denied, nothing to do.

**Done via automation API** (highest-value denies, cleanly): 4 `block in log quick` rules - **IoT/Guest/Lab → Local_Nets** and **LAN → VLAN20 (BMC)**. They mirror the existing silent blocks exactly (same drop) but **log**, and because automation rules evaluate first they supersede the old silent manual blocks (which become dead). Verified in `/tmp/rules.debug` (IoT example): `pass Pi_holes:53` @228 → `block **log** Local_Nets` @232 → dead manual block @247. So DNS still passes, lateral is logged+dropped, isolation intact.

**Done in GUI (in-place "Log" tick):** TRUSTED(opt1), SERVERS(opt2 ×2), VoIP(opt4) blocks - these interfaces have *allow* rules that must stay ahead of the block (trusted→mgmt/servers; servers→Pi-hole DNS; voip→servers), so an automation block would preempt them. Logged in place instead: **Firewall → Rules → [iface]** → edit each `block` rule → tick **Log**. **Verified 2026-07-11: ALL 8 VLAN denies now log** (4 via automation LOG rules, 4 via manual in-place Log flag).

**Deliberately skipped (proportionate, not gold-plating):** IoT/Guest egress port-restriction (breaks smart-home devices); VoIP→FreePBX tightening (FreePBX not deployed); TRUSTED/SERVERS egress limits (breaks server workloads).

**Rollback:** delete the 4 automation block-log rules (drop reverts to the silent manual blocks - same isolation, just no logging).
