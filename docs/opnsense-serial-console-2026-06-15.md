# OPNsense VM — Serial Console Addition
**Date:** June 15, 2026  
**Node:** pve2  
**VM:** 100 (OPNsense)

---

## Background

During the network outage on 2026-06-14, `qm terminal 100` failed with:
```
unable to find a serial interface
```

This made emergency console access to OPNsense impossible without a working network. Serial console was added the following day as a direct lesson from that incident.

---

## What Was Done

### Step 1 — Fix VM config file permissions
The Proxmox UI returned a permission error when attempting to edit VM 100 hardware:
```
unable to open file '/etc/pve/nodes/pve2/qemu-server/100.conf.tmp.2045' - Permission denied (500)
```

Root cause: config file had read-only permissions.
```bash
ls -la /etc/pve/nodes/pve2/qemu-server/100.conf
# -r--r----- 1 root www-data 411
```

Fix:
```bash
chmod 640 /etc/pve/nodes/pve2/qemu-server/100.conf
```

### Step 2 — Add Serial Port in Proxmox UI
```
VM 100 → Hardware → Add → Serial Port → Port 0
```

### Step 3 — Enable Serial Console in OPNsense
```
VM 100 → Console (Proxmox UI)
OPNsense menu → System → Settings → Administration
Console → Serial Console → Enable → Save → Apply
```

---

## Result

`qm terminal 100` now works from pve2 shell, providing emergency console access to OPNsense independent of network connectivity.

```bash
# Emergency OPNsense access going forward:
qm terminal 100
# Press Enter if no prompt appears
# To exit: Ctrl+]
```

---

## Why This Matters

Without serial console, the only way into OPNsense during a network outage is:
- Proxmox web UI (requires network)
- VNC via socat tunnel (complex, requires tools installed)
- Physical monitor on the host (no direct VM display)

Serial console eliminates all of those dependencies.
