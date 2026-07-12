# WAN Failover — FirstNet Netgear MR7400 → OPNsense WAN2

**Status:** 🟡 PLANNED — build when back at the keyboard (physical cabling required). Nothing changed live as of 2026-07-12.
**Goal:** Hard-wire the AT&T FirstNet MR7400 LTE hotspot as an automatic **whole-network** internet failover, so all VLANs keep outbound connectivity when the primary WAN drops.
**Related:** [[DNS-HA-OPNsense-Resilience-2026-07-10]], [[Security-VLAN-Segmentation-Phased-2026-07-03]], [[Network-Performance-and-Upgrade-Path-2026-07-09]]

---

## Hardware
- **Hotspot:** Netgear Nighthawk **MR7400** (AT&T FirstNet). SW `MR7400-1A1NAS_O4.17`, firmware `NTGX75_10.04.43.00`. Single **2.5 GbE** Ethernet port; **default** DHCP LAN is `192.168.1.0/24`. ⚠️ **CONFLICT** — OPNsense LAN carries a legacy `192.168.1.1/24` IP-alias ("Legacy Proxmox Network"), so `192.168.1.0/24` is already in use. **Re-subnet the hotspot to `192.168.150.0/24`** before connecting (see Part A).
- **Router:** OPNsense **VM 100** on **pve2** (`192.168.10.204`), `onboot=1`.

## Architecture
```
MR7400 (FirstNet)          pve2                         OPNsense VM 100
 2.5G Eth ──cable──►  nic2 (I350 port1) ──► vmbr2 ──► net2 → WAN2 (DHCP → 192.168.150.x)
 DHCP 192.168.150.0/24     (no host IP, plain bridge)        │
 (re-subnetted from .1.x)                                    │
                                                             ▼
                                                   Gateway Group "FAILOVER"
                                                     WAN  = Tier 1 (primary)
                                                     WAN2 = Tier 2 (LTE)
```

---

## Verified facts (read-only recon, 2026-07-12)

### pve2 NICs
| Link | Hardware | Bus | Bridge | Role |
|---|---|---|---|---|
| `nic0` | Intel I219-LM (onboard) | `00:1f.6` | `vmbr0` (no IP) | **Primary WAN** → OPNsense `net0` |
| `nic1` | Intel I350 port 0 | `01:00.0` | `vmbr1` (VLAN-aware, host .204) | **LAN trunk** → OPNsense `net1` (trunks 1–70) |
| **`nic2`** | **Intel I350 port 1** | `01:00.1` | **none** (`vmbr2` disabled) | **FREE — down, no carrier. Use this.** |

- `nic2` MAC `b4:96:91:90:85:d5`, driver `igb`. Its bridge `vmbr2` was disabled 2026-06-25 (caused a VLAN trunk loop **when patched into the EX3400**). Point-to-point to the hotspot = **no loop risk**. Do **not** cable it into the switch.
- WAN is **bridge-attached, not PCI-passthrough** → we mirror that pattern for WAN2 (no passthrough needed).

### OPNsense VM 100 (current)
```
net0: virtio,bridge=vmbr0                 # WAN
net1: virtio,bridge=vmbr1,trunks=1-70     # LAN trunk
```

### OPNsense addressing (API-verified 2026-07-12, read-only backup+rw keys)
| Interface | Device | Subnet |
|---|---|---|
| WAN | vtnet0 | `173.91.172.132/19` — **public IP** (DHCP), no `192.168.1.x` here |
| LAN | vtnet1 | `192.168.10.1/24` **+ `192.168.1.1/24` IP-alias VIP ("Legacy Proxmox Network")** ⚠️ |
| TRUSTED (opt1) | vlan01 | `192.168.20.1/24` |
| SERVERS (opt2) | vlan02 | `192.168.30.1/24` |
| IOT (opt3) | vlan03 | `192.168.40.1/24` |
| VoIP (opt4) | vlan04 | `192.168.50.1/24` |
| GUEST (opt5) | vlan05 | `192.168.60.1/24` |
| LAB (opt6) | vlan06 | `192.168.70.1/24` |

- **`192.168.1.0/24` is the collision** → hotspot must be re-subnetted to `192.168.150.0/24` (Part A step 6). `.150` is clear of every subnet above.
- The legacy `192.168.1.1/24` VIP is vestigial (Proxmox now on `.10`). Retiring it is a *separate, deliberate* change — do NOT delete blind; check for references first.
- API creds: read-only backup key `~/.config/opnsense-backup/api.env` (config download only); `~/.config/opnsense-api/rw.env` for live diagnostics GETs. Host `192.168.10.1` (also answers on `.30.1`).

### Headscale (context for remote access)
- v0.29.1, LXC **105** on **pve3**, IP `192.168.10.186`. Reach via `ssh pve3 'pct exec 105 -- …'` (direct SSH key not authorized).
- `server_url: http://192.168.10.186:8080` (**LAN-only** control plane), `base_domain: netframe.local`.
- `derp.server.enabled: false`; `derp.urls: controlplane.tailscale.com/derpmap/default` → **already relaying via Tailscale's public DERP**. Never-expire keys.

---

## Part A — MR7400 hotspot config
1. Connect to the hotspot admin (Wi-Fi to it, or the app) → `http://192.168.1.1` / `attwifimanager`. Admin password on the device label.
2. **Enable the Ethernet port** for data (default is LAN/DHCP — what we want).
3. Set **"always on when powered"** (disable sleep/battery-save power-off).
4. **Turn Wi-Fi radios OFF** — we only use Ethernet; cuts heat, power draw, attack surface.
5. Keep it on **AC power permanently**.
6. ⚠️ **REQUIRED — change the hotspot LAN/DHCP subnet `192.168.1.0/24` → `192.168.150.0/24`** (hotspot becomes `192.168.150.1`). OPNsense LAN already has a legacy `192.168.1.1/24` IP-alias; leaving the hotspot on `192.168.1.x` collides and breaks WAN2 routing.

## Part B — pve2 wiring
```bash
# 1. Positively ID the physical jack BEFORE cabling:
ssh pve2 'ethtool -p nic2 30'          # blinks nic2's LED 30s — that's the port

# 2. Cable the blinking I350 port (nic2) → MR7400 Ethernet. NOT into the switch.

# 3. Re-enable the bridge on nic2 (plain, no VLAN, no host IP):
#    /etc/network/interfaces — uncomment `auto vmbr2`, keep:
#      auto vmbr2
#      iface vmbr2 inet manual
#              bridge-ports nic2
#              bridge-stp off
#              bridge-fd 0
ssh pve2 'ifup vmbr2'

# 4. Add a 3rd NIC to OPNsense on that bridge:
ssh pve2 'qm set 100 -net2 virtio,bridge=vmbr2'
```
> ⚠️ **virtio hot-plug on FreeBSD is unreliable.** If OPNsense doesn't see `vtnet2` live, it needs a reboot — which drops internet for the **whole network** ~1 min. Do steps 4 + Part C in a short planned window.

## Part C — OPNsense WAN2 + failover
1. **Interfaces → Assignments:** new NIC appears (`vtnet2`) → add → name **WAN2** (or LTE). Enable → IPv4 = **DHCP**.
2. **System → Gateways → Configuration:** a `WAN2_DHCP` gateway auto-creates. Edit → set **Monitor IP** `1.1.1.1` (so link health is sensed) → priority **lower** than primary WAN.
3. **System → Gateways → Group:** new group **FAILOVER** → `WAN` = **Tier 1**, `WAN2` = **Tier 2**, Trigger = **Member down** (or *Packet Loss or High Latency*).
4. **Firewall → NAT → Outbound:** ensure it covers WAN2 (Automatic mode auto-generates all WANs; if Hybrid/Manual, add a WAN2 rule).
5. **Firewall → Rules → LAN and each VLAN:** on the "allow → any" internet rule, **Advanced → Gateway = FAILOVER**. ← *the step that actually makes traffic fail over. Repeat per VLAN internet rule.*
6. **Interfaces → WAN2:** set **MSS 1400** (avoids cellular MTU black-holing).
7. **System → Settings → Miscellaneous:** enable **"State Killing on Gateway Failure"** + **"Use sticky connections"** for a clean cutover.
8. **DNS:** confirm Pi-hole upstreams (.177/.178) resolve over failover; if OPNsense Unbound has outgoing interfaces pinned to WAN, set to **all**.

## Part D — Test the failover
1. Dashboard → **Gateways** widget shows both, correct tiers.
2. **Pull the primary WAN** (unplug nic0 / disable WAN iface). Watch WAN go down → group shift to WAN2. Confirm a LAN client keeps internet + DNS.
3. `tailscale netcheck` from a client — confirm relay path works.
4. **Restore** primary → confirm failback.
5. ⚠️ **Mind the FirstNet data cap** — emergency use only, not bulk traffic.

---

## Remote access during an outage
**Finding:** the tailnet already relays via **Tailscale's public DERP** + **never-expire keys**, so once failover restores home's outbound uplink, **phone→home access recovers on its own** — no new relay strictly required. The failover build *is* the remote-access fix.

**Continuing a Claude Code session from phone:** `--remote-control` (Claude Code v2.1.207) relays **outbound** through claude.ai — survives CGNAT, needs no VPN. Started this session with `/remote-control Homelab-Failover`.

### Optional hardening — self-hosted DERP (independence from Tailscale infra)
Not required for function; completes the off-Tailscale migration + guarantees relay availability/privacy.
- **VPS:** 1 vCPU / 1 GB, **US region** (Hetzner Ashburn CPX11 ~€4.4/mo or DO NYC $4–6). Public IPv4. DNS: `derp.kylemason.org A <VPS_IP>`. Open **443/tcp, 80/tcp, 3478/udp**.
- **On VPS:**
  ```bash
  apt update && apt install -y golang-go
  go install tailscale.com/cmd/derper@latest      # → /root/go/bin/derper
  ```
  ```ini
  # /etc/systemd/system/derper.service
  [Service]
  ExecStart=/root/go/bin/derper --hostname=derp.kylemason.org \
    --certmode=letsencrypt --certdir=/var/lib/derper \
    -a :443 --http-port=80 --stun --verify-clients=false
  Restart=always
  [Install]
  WantedBy=multi-user.target
  ```
  `systemctl enable --now derper`
- **On Headscale** (`ssh pve3 'pct exec 105 -- …'`): create `/etc/headscale/derp-homelab.yaml`:
  ```yaml
  regions:
    900:
      regionid: 900
      regioncode: homelab
      regionname: "Homelab VPS"
      nodes:
        - name: 900a
          regionid: 900
          hostname: derp.kylemason.org
          ipv4: <VPS_IP>
          stunport: 3478
          stunonly: false
          derpport: 443
  ```
  In `/etc/headscale/config.yaml` — keep the Tailscale URL as fallback, add the path:
  ```yaml
  derp:
    urls:
      - https://controlplane.tailscale.com/derpmap/default
    paths:
      - /etc/headscale/derp-homelab.yaml
  ```
  `systemctl restart headscale`. Verify with `tailscale netcheck` (region `homelab/900` should appear with latency).

---

## When-back checklist
- [ ] MR7400: enable Ethernet, always-on, Wi-Fi off, on AC power
- [ ] `ethtool -p nic2` → ID physical jack → cable to MR7400 (NOT the switch)
- [ ] pve2: uncomment `auto vmbr2`, `ifup vmbr2`
- [ ] `qm set 100 -net2 virtio,bridge=vmbr2` (planned window — may need OPNsense reboot)
- [ ] OPNsense: assign WAN2 (DHCP) → monitor IP → FAILOVER group → gateway on LAN/VLAN rules → MSS 1400 → state-kill/sticky
- [ ] Test: pull primary → verify failover + DNS → restore → verify failback
- [ ] (Optional) Stand up VPS DERP + register in Headscale
- [ ] Update monitoring: add a WAN2/gateway-down alert (Grafana → Discord) — see [[Monitoring-Alerting-2026-07-10]]
