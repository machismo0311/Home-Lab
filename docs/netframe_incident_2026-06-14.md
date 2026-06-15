# NetFRAME Homelab — Session Log & Incident Report
**Date:** June 14–15, 2026  
**Node:** pve2 (HP EliteDesk G4 SFF, i7-8700, 48GB RAM)  
**Session Goal:** Install step-ca internal CA on pve2  
**Outcome:** Internet restored, pve2 management stabilized at 192.168.10.204

---

## System State at Start of Session

### pve2 Network (Before Changes)
```
vmbr0: inet manual — bridge-ports nic0 (OPNsense WAN → modem)
vmbr1: inet manual — bridge-ports nic1 (OPNsense LAN → EX3400)
vmbr2: inet static 192.168.10.200/24 gw 192.168.10.1 — bridge-ports nic2
```

**Known conflict at session start:** vmbr2 had 192.168.10.200 assigned on the Proxmox host, which is also OPNsense's LAN IP. This was a pre-existing ARP conflict that was "working by luck."

### OPNsense VM (ID 100)
```
net0 (vtnet0) → vmbr0 → nic0 → modem (WAN, DHCP from ISP)
net1 (vtnet1) → vmbr1 → nic1 → EX3400 Panel B port 16 (LAN)
LAN IP: 192.168.10.1 (gateway for all homelab devices)
Management IP: 192.168.10.200
```

### IP Map (192.168.10.0/24)
```
.1    = OPNsense LAN (gateway)
.50   = Juniper EX3400 IRB (management)
.100  = Ares (admin workstation)
.193  = pve1 (Mac mini)
.199  = Ares wired interface
.200  = OPNsense VM management (CONFLICTED with pve2 host on vmbr2)
.201  = pve3 (G4 SFF)
.202  = pve4 (G3 Mini)
.203  = pve5 (G3 Mini)
.204  = pve2 host (NEW — assigned this session)
```

### Patch Panel B (Juniper EX3400 side)
```
Port 9:  pve1 (Mac mini)
Port 10: pve5 (G3 Mini)
Port 11: pve4 (G3 Mini)
Port 12: pve3 (G4 SFF)
Port 13: iDRAC R730 #1
Port 14: iDRAC R730 #2
Port 15: SuperMicro IPMI
Port 16: OPNsense NIC1 (LAN, vmbr1/nic1)
Port 17: Middle Atlantic UPS-OL2200R
Port 18: APC AP7901 PDU
Port 19: OPNsense NIC2 (unknown EX3400 port mapping)
Port 25: Trunk to EX3400 port 1 (inter-switch uplink)
```

---

## Part 1: step-ca Installation

### Goals
- Install Smallstep step-ca on pve2 as an internal CA
- Issue TLS certs for `*.netframe.local` services
- Distribute root CA to all homelab devices

### Issue: DNS not resolving on pve2
`/etc/resolv.conf` pointed at Pi-hole at `192.168.1.170` (old subnet).  
pve2 was on `192.168.10.x` and couldn't reach it.

**Fix:**
```bash
echo "nameserver 8.8.8.8" > /etc/resolv.conf
```

### Installation
```bash
wget https://dl.smallstep.com/cli/docs-cli-install/latest/step-cli_amd64.deb
dpkg -i step-cli_amd64.deb
wget https://dl.smallstep.com/certificates/docs-ca-install/latest/step-ca_amd64.deb
dpkg -i step-ca_amd64.deb
```

Versions installed:
- step CLI: 0.30.6
- step-ca: 0.30.2

### CA Initialization
```bash
step ca init \
  --name "NetFRAME Internal CA" \
  --dns "ca.netframe.local" \
  --address ":443" \
  --provisioner "admin@netframe.local"
```

**Deployment type:** Standalone  
**Password:** auto-generated (saved to key files)

**Output:**
```
Root certificate:         /root/.step/certs/root_ca.crt
Root private key:         /root/.step/secrets/root_ca_key
Root fingerprint:         ac379085e7e9dfdfa5cd82704a6f050fe09d02018e61f6333952a9c398e9dbec
Intermediate certificate: /root/.step/certs/intermediate_ca.crt
Intermediate private key: /root/.step/secrets/intermediate_ca_key
Database:                 /root/.step/db
Config:                   /root/.step/config/ca.json
```

### ACME Provisioner
```bash
step ca provisioner add acme --type ACME
```

### System User and Config Migration
```bash
useradd --system --home /etc/step-ca --shell /bin/false step
mkdir -p /etc/step-ca
cp -r /root/.step/* /etc/step-ca/
chown -R step:step /etc/step-ca
```

### Systemd Service
```bash
cat > /etc/systemd/system/step-ca.service << 'EOF'
[Unit]
Description=NetFRAME Internal CA
After=network.target

[Service]
User=step
Environment=STEPPATH=/etc/step-ca
ExecStart=/usr/bin/step-ca /etc/step-ca/config/ca.json
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

### Issue: Database path wrong
Error: `error opening Badger database`  
Config still pointed to `/root/.step/db` instead of `/etc/step-ca/db`.

**Fix:**
```bash
sed -i 's|/root/.step|/etc/step-ca|g' /etc/step-ca/config/ca.json
systemctl restart step-ca
systemctl enable step-ca
```

**Result:** step-ca running successfully as systemd service.

---

## Part 2: Network Incident

### Root Cause
Claude (AI assistant) suggested moving pve2's management IP without first reviewing patch panel diagrams and NIC assignments from prior sessions. This led to a series of incorrect interface changes that caused a full homelab internet outage lasting approximately 2 hours.

### Pre-existing Conflict (discovered during session)
vmbr2 had `192.168.10.200/24` assigned on the Proxmox host. OPNsense LAN interface also uses `192.168.10.200`. This was a Layer 2 ARP identity collision that was "working by luck" before the session.

---

### Timeline of Changes and Errors

#### Attempt 1: Move management to vmbr0 (WRONG)
Claude incorrectly put pve2 management IP on vmbr0 — which is the OPNsense WAN bridge connected to the modem. This meant pve2 was trying to route through the modem directly, bypassing OPNsense entirely.

**Result:** No connectivity. SSH lost.

#### Attempt 2: Move management to vmbr1 with gateway .200 (WRONG)
Claude moved management to vmbr1 (OPNsense LAN bridge) but set gateway to `192.168.10.200` (OPNsense's management IP) instead of `192.168.10.1` (OPNsense's LAN IP). Also set vmbr2 back to static .200, recreating the ARP collision.

**Result:** Two interfaces in same subnet, two competing gateways, ARP collision. OPNsense WAN stopped acquiring DHCP lease. Full internet outage.

#### Multiple failed recovery attempts
- `ip route del/add` commands — default route kept reverting to vmbr1
- `qm restart 100` — OPNsense restarted but WAN still down
- `qm terminal 100` — failed: no serial console configured on VM
- `qm guest exec 100` — failed: no QEMU guest agent installed
- `qm vncproxy 100` — failed: no LC_PVE_TICKET set
- Modem reboot — no effect (modem is bridge-only, not router)
- Connecting laptop via small switch — limited connectivity, couldn't SSH to pve2

#### Recovery: ChatGPT diagnosis
Incident report document shared with ChatGPT. Diagnosis:

**3 overlapping problems:**
1. Two interfaces in same /24 subnet with competing gateways
2. .200 reused on both Proxmox host (vmbr2) and OPNsense LAN — Layer 2 ARP collision
3. Gateway set to .200 (OPNsense management IP) not .1 (OPNsense LAN IP)

---

### Successful Recovery

**Final working `/etc/network/interfaces`:**
```
auto lo
iface lo inet loopback

# WAN (to modem via OPNsense)
auto vmbr0
iface vmbr0 inet manual
        bridge-ports nic0
        bridge-stp off
        bridge-fd 0

# LAN (main management + OPNsense LAN side)
auto vmbr1
iface vmbr1 inet static
        address 192.168.10.204/24
        gateway 192.168.10.1
        bridge-ports nic1
        bridge-stp off
        bridge-fd 0

# Spare NIC (no host IP)
auto vmbr2
iface vmbr2 inet manual
        bridge-ports nic2
        bridge-stp off
        bridge-fd 0

source /etc/network/interfaces.d/*
```

**ARP cleanup:**
```bash
ip addr flush dev vmbr2
ip neigh flush all
systemctl restart networking
```

**Result:** Routing stabilized, OPNsense WAN re-acquired DHCP lease, internet restored.

---

## Part 3: Known Issues Remaining

### 1. OPNsense VM has no serial console
`qm terminal 100` fails with "unable to find a serial interface."  
This made emergency console access impossible during the outage.

**Fix (pending):**
```
Proxmox UI → VM 100 → Hardware → Add → Serial Port → Port 0
Then in OPNsense: System → Settings → Administration → enable serial console
```

**Current blocker:** Proxmox UI returns permission error when trying to edit VM 100 hardware:
```
unable to open file '/etc/pve/nodes/pve2/qemu-server/100.conf.tmp.2045' - Permission denied (500)
```

**Root cause:** VM config file has wrong permissions:
```bash
ls -la /etc/pve/nodes/pve2/qemu-server/100.conf
# -r--r----- 1 root www-data 411
```

**Fix:**
```bash
chmod 640 /etc/pve/nodes/pve2/qemu-server/100.conf
```

Then retry adding serial port in Proxmox UI.

### 2. step-ca DNS entry not created
`ca.netframe.local` has no DNS A record in Pi-hole yet.  
Pi-hole needs: `ca.netframe.local → 192.168.10.204`

### 3. Root CA not distributed
`/etc/step-ca/certs/root_ca.crt` needs to be copied to all nodes and browsers.

```bash
# On each Debian node:
scp root@192.168.10.204:/etc/step-ca/certs/root_ca.crt /usr/local/share/ca-certificates/netframe-root-ca.crt
update-ca-certificates
```

### 4. pve2 resolv.conf set to 8.8.8.8
Should be updated to internal Pi-hole once Pi-hole is migrated to LXC on VLAN 20.

---

## Lessons Learned

1. **Search prior conversation history before suggesting network changes.** Patch panel diagrams and NIC assignments were documented and would have prevented this entire incident.
2. **Eliminate Layer 2 conflicts before investigating higher-layer services.** The WAN DHCP failure was a symptom, not the root cause.
3. **Simplify before diagnosing.** The fix required removing complexity, not adding it.
4. **Never assign a host IP to a bridge that also carries a VM interface in the same subnet.**
5. **One subnet = one management identity per device.**
6. **Gateway must always be the router IP (.1), never the VM management IP (.200).**
7. **Add serial consoles to all VMs.** `qm terminal` is essential for emergency access.
8. **Add QEMU guest agent to all VMs.** Enables `qm guest exec` for emergency commands.

---

## Known Good State (End of Session)

| Item | Value |
|------|-------|
| pve2 management IP | 192.168.10.204 |
| pve2 Proxmox UI | https://192.168.10.204:8006 |
| OPNsense gateway | 192.168.10.1 |
| OPNsense management | 192.168.10.200 |
| EX3400 management | 192.168.10.50 |
| Internet | Restored |
| step-ca | Running at /etc/step-ca, service enabled |
| step-ca root fingerprint | ac379085e7e9dfdfa5cd82704a6f050fe09d02018e61f6333952a9c398e9dbec |
| JunOS version | 23.4R2-S7.4 |
| VLANs on EX3400 | 1/20/30/40/50/60/70 defined |
