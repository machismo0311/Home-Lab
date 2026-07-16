# Home Assistant OS Install - VM 110 on pve5 (2026-07-16)

**Tags:** #runbook #homeassistant #iot #pve5
**Related:** [[Infrastructure/Services & VMs]] · [[Infrastructure/Proxmox Cluster]] · [[Networking/Network Overview]]

---

## Summary

Home Assistant OS (HAOS) 18.1 installed as a full appliance VM on pve5. HAOS (not Core-in-LXC, not Container) was chosen deliberately: it is the only install type that ships the **Supervisor and add-on store**, which is what future planning needs - Mosquitto MQTT, Zigbee2MQTT, ESPHome, Node-RED, Matter server etc. all install as one-click add-ons and get managed updates and native HA backups.

| Field | Value |
|---|---|
| VM | **110** `homeassistant` on pve5 (192.168.10.203) |
| OS | HAOS 18.1 (haos_ova qcow2, generic-x86-64) |
| Firmware | OVMF (UEFI), `pre-enrolled-keys=0` (HAOS is not Secure Boot signed - never enroll keys) |
| CPU / RAM | 2 cores `cpu: host`, 4096 MB, `balloon: 0` (HAOS does not play well with ballooning) |
| Disk | scsi0 on local-lvm (thin), imported 32G image resized to **64G**; `discard=on,ssd=1`; efidisk0 4M |
| NIC | virtio on vmbr0 (VLAN 1), MAC **BC:24:11:27:B2:5C** |
| IP | **192.168.10.60** via OPNsense DHCP static mapping (added same day; first boot briefly held pool address .153) |
| DNS | `homeassistant.netframe.local` → .60 on primary Pi-hole (nebula-sync mirrors to .178) |
| URL | http://homeassistant.netframe.local:8123 |
| Boot | `onboot=1`; qemu-guest-agent is built into HAOS (`agent: enabled=1`, verified responding) |
| Backup | Daily vzdump 03:30 → `randy-pbs`, keep-daily=7 keep-weekly=4 (own job in jobs.cfg); first manual backup run at install time |
| Tag | `iot` |

## Install procedure (repeatable)

```bash
# on pve5
cd /var/tmp
curl -sLo haos.qcow2.xz https://github.com/home-assistant/operating-system/releases/download/18.1/haos_ova-18.1.qcow2.xz
unxz haos.qcow2.xz

qm create 110 --name homeassistant --ostype l26 --bios ovmf --cpu host \
  --cores 2 --memory 4096 --balloon 0 --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci --agent enabled=1 --tablet 0 --localtime 1 --onboot 1 --tags iot
qm set 110 --efidisk0 local-lvm:1,efitype=4m,pre-enrolled-keys=0
qm set 110 --scsi0 local-lvm:0,import-from=/var/tmp/haos.qcow2,discard=on,ssd=1
qm set 110 --boot order=scsi0
qm resize 110 scsi0 64G
qm start 110          # HAOS grows its data partition to fill 64G on first boot
qm agent 110 network-get-interfaces   # get the DHCP IP once the agent answers (~40 s)
```

HAOS updates itself from the UI (Settings → System → Updates); never reinstall to upgrade.

## Verification (done at install)

- `qm agent 110 ping` responds; IP reported on `enp0s18`
- `http://192.168.10.153:8123/` returns HTTP 200 (onboarding page)
- `dig homeassistant.netframe.local @192.168.10.177` → 192.168.10.153
- Manual vzdump to randy-pbs succeeded; scheduled job present in `/etc/pve/jobs.cfg`
- pve5 headroom after install: ~20 GiB RAM free with CT 108 + VM 203 + VM 110 running

## Owner follow-ups (in OPEN-ITEMS)

1. **Onboarding:** browse to http://homeassistant.netframe.local:8123 and create the owner account (first visit claims the instance - do it soon). File credentials in Vaultwarden.
2. ~~DHCP static mapping~~ **DONE 2026-07-16:** MAC `BC:24:11:27:B2:5C` → `192.168.10.60` (Services → ISC DHCPv4 → LAN → static mappings). Verified by VM reboot picking up .60. Two gotchas found:
   - **In-pool static maps are rejected**: the LAN pool is .100-.199 and the GUI refuses a mapping at .153 (the form silently redisplays with a validation error that is easy to miss). Use an address outside the pool; .60 was verified free first. (The .177/.178 Pi-hole mappings inside the pool predate this validation path.)
   - **`/api/core/backup/download/this` served a stale config**: even after the mapping was live (VM re-leased .60), the endpoint kept returning the 2026-07-13 revision without it. The nightly `opnsense-config-backup` uses this same endpoint - verify the next nightly backup contains the mapping (tracked in OPEN-ITEMS).
3. **Add-ons when wanted:** Mosquitto broker (MQTT), ESPHome, Zigbee2MQTT / Z-Wave JS as hardware arrives. All via Settings → Add-ons.

## Future planning notes

- **Zigbee/Z-Wave USB stick:** pve5 is the HA host, so plug the coordinator (e.g. SONOFF ZBDongle-E / Aeotec Z-Stick) into pve5 and pass it through: `qm set 110 --usb0 host=<vendor:product>,usb3=0` (serial-by-id passthrough survives re-plugs better than port mapping). Prefer a USB extension cable away from the chassis for Zigbee RF.
- **IoT VLAN 40:** HA sits on VLAN 1 (mgmt) today because that is where pve5's bridge is. IoT devices belong on VLAN 40; when the first ones arrive, add OPNsense rules allowing HA (.60) → VLAN 40 (and mDNS/SSDP reflection via the Avahi/udpbroadcastrelay approach, or use the HA integrations that take static IPs). Alternative later: trunk pve5's switch port and give VM 110 a second NIC tagged VLAN 40.
- **HA native backups:** in addition to the nightly PBS image backup, configure HA's own backup (Settings → System → Backups) for app-level restores; a Samba/NFS target on Randy would keep copies off-host. PBS covers DR either way.
- **Reverse proxy / TLS:** optional NPM proxy host (id on .181) + Let's Encrypt if remote or HTTPS access is wanted; HA needs `http:` `use_x_forwarded_for: true` + `trusted_proxies: 192.168.10.181` in configuration.yaml when proxied.
- **Voice / local LLM:** HA Assist can point at an OpenAI-compatible endpoint - llm_router on Jarvis (`http://llm.netframe.local`) is a natural fit later.
- **Monitoring:** VM 110 is auto-discovered by netframe_monitor guest liveness (`qm list`). Grafana Proxmox widgets pick it up via the cluster API. A dedicated HA integration for Prometheus exists if metrics are ever wanted.

## Rollback

`qm stop 110 && qm destroy 110 --purge` (removes it from the backup job too), delete the Pi-hole `dns.hosts` entry for homeassistant.netframe.local, and remove the 03:30 vzdump job from Datacenter → Backup. Nothing else on pve5 was touched.
