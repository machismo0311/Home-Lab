# Home Assistant Integrations - Full Homelab Wire-Up (2026-08-05)

**Tags:** #runbook #homeassistant #iot #integrations
**Related:** [[Runbook/Home-Assistant-Install-2026-07-16]] · [[Infrastructure/Services & VMs]] · [[Jarvis-LLM-Platform-2026-07-05]]

---

## Summary

HA (VM 110, `192.168.10.60`, HAOS/core **2026.7.2**) was a near-stock install: onboarding
defaults plus a few auto-discovered consumer devices (Samsung TV, Brother printer, Xbox). This
runbook wires the homelab into it: local-AI assistant on Jarvis, Proxmox, Pi-hole, UPS/NUT,
Jellyfin, OPNsense, Speedtest, and a metrics export back into the existing Grafana.

**Constraint / handoff note:** adding integrations is a live change to a prod service and is
blocked by the session change-classifier, and most HA integrations are UI config-flows anyway.
So every step below is **operator-applied**. Credentials are created by you and never pasted into
this (public) runbook - only their source location is referenced.

### Apply order (dependencies first)

| Step | Item | Type | Credential needed |
|---|---|---|---|
| 0 | **DNS fix** (resolve `*.netframe.local` from HA) | HAOS console | none |
| 1 | HACS install (unlocks community integrations) | HAOS console | GitHub (device flow) |
| 2 | **Local AI assistant** (llm_router on Jarvis) | HACS + UI | none (open endpoint) |
| 3 | Proxmox VE | UI | PVE API token (created below) |
| 4 | NUT (UPS) | UI | existing `monuser` on pve3 |
| 5 | Pi-hole x2 | UI | app-password (created below) |
| 6 | Jellyfin | UI | API key (created below) |
| 7 | OPNsense | HACS + UI | API key/secret (created below) |
| 8 | Speedtest.net | UI | none |
| 9 | Prometheus export -> Grafana | YAML + Prometheus | HA long-lived token |
| 10 | Enable discovered devices | UI | none |
| - | Optional: HA backups -> Randy, MQTT, SNMP, SSH add-on | mixed | see notes |

Reach the HAOS console via the pve5 web UI -> VM 110 -> Console (noVNC). At the `ha >` prompt type
`login` for the host root shell (`#`). VM 110 has **no serial port**, so `qm terminal 110` fails.

---

## Step 0 - DNS fix (prerequisite)

HAOS's Supervisor DNS falls back to public resolvers, so local names like `llm.netframe.local`
fail inside the HA container even though `resolv.conf` lists Pi-hole. Force Pi-hole-only:

```bash
# HAOS console (ha > prompt, NOT the root shell)
ha dns options --servers dns://192.168.10.177 --servers dns://192.168.10.178 --fallback false
ha dns restart
```

**Verify** (host root shell after `login`):
```bash
docker exec homeassistant python3 -c "import socket;print(socket.gethostbyname('llm.netframe.local'))"
# expect 192.168.10.181 (NPM), not an error
```

---

## Step 1 - HACS (Home Assistant Community Store)

Unlocks the AI-conversation and OPNsense integrations (steps 2 and 7).

```bash
# HAOS host root shell (# after `login`)
docker exec homeassistant bash -c "wget -O - https://get.hacs.xyz | bash -"
docker restart homeassistant
```
Then in HA: **Settings -> Devices & Services -> Add Integration -> HACS**, tick the boxes, and
complete the GitHub device-code login it shows.

---

## Step 2 - Local AI assistant (Jarvis llm_router)

llm_router (`http://llm.netframe.local`, OpenAI-compatible, models `qwen2.5:72b` and `rag`) is
reachable from HA and needs no key. The `rag` model grounds answers on the Home-Lab vault. HA's
core OpenAI integration can't take a custom base URL, so use the HACS **Extended OpenAI
Conversation**.

1. HACS -> Integrations -> search **Extended OpenAI Conversation** -> Download -> restart HA.
2. Settings -> Devices & Services -> Add -> **Extended OpenAI Conversation**:
   - **Base URL:** `http://llm.netframe.local/v1`
   - **API key:** any non-empty string (endpoint is open on the LAN)
   - **Model:** `rag` (vault-grounded) or `qwen2.5:72b` (general)
3. Settings -> Voice assistants -> Assist -> set **Conversation agent** to Extended OpenAI.
4. **Verify:** open Assist (top-left chat icon) and ask "what nodes are in km-cluster?" - `rag`
   should answer from the vault.

> Alt path (no HACS): expose Ollama on Jarvis to the LAN (`OLLAMA_HOST=0.0.0.0:11434` +
> firewall) and use HA's core **Ollama** integration at `http://192.168.10.31:11434`. Requires a
> Jarvis service change; the llm_router path above avoids touching Jarvis and adds RAG.

---

## Step 3 - Proxmox VE

Monitors all 7 nodes + VMs/LXCs (up/down, CPU, RAM, disk). Create a read-only token on any
cluster node (operator-applied on Proxmox):

```bash
# on a cluster node, e.g. ssh root@192.168.10.201
pveum user add homeassistant@pve
pveum acl modify / --user homeassistant@pve --role PVEAuditor
pveum user token add homeassistant@pve ha --privsep 0    # prints the token secret ONCE - copy it
```
HA: Add Integration -> **Proxmox VE** -> Host `192.168.10.201`, Port `8006`, User
`homeassistant@pve`, Token name `ha`, Token secret `<from above>`, **Verify SSL: off**
(self-signed) -> pick the nodes/guests to track. File the secret in Vaultwarden.

---

## Step 4 - NUT (UPS)

The NUT server (`upsd`) runs on **pve3** (`192.168.10.201:3493`, listening on the LAN) with two
UPSes: **`tripplite`** (SMART1500 - networking/small compute) and **`midatlantic`**
(UPS-OL2200R - R730s/Randy/DS4246). User **`monuser`** already exists.

HA: Add Integration -> **Network UPS Tools (NUT)** -> Host `192.168.10.201`, Port `3493`,
Username `monuser`, Password `<value in /etc/nut/upsd.users on pve3>` -> select both UPSes.
Gives battery %, load, input voltage, runtime, and status (feeds "on battery" automations).

---

## Step 5 - Pi-hole (x2, HA DNS pair)

Pi-hole v6 needs an app-password token. In each Pi-hole admin (`http://192.168.10.177/admin` and
`.../178`): **Settings -> All settings -> Web interface / API -> Generate app password** (see the
[[homepage-location-and-pihole-widget]] note - v6 app-password gotcha).

HA: Add Integration -> **Pi-hole** twice:
- Host `192.168.10.177`, API key `<app password>`, **uncheck** "statistics only" (enables the
  disable/enable switch).
- Repeat for `192.168.10.178`.

---

## Step 6 - Jellyfin

Reachable at `http://192.168.10.187:8096`. Create a key: Jellyfin **Dashboard -> Advanced -> API
Keys -> +** (name it `home-assistant`).

HA: Add Integration -> **Jellyfin** -> URL `http://192.168.10.187:8096`, API key `<above>`.
Now-playing / library / user sensors.

---

## Step 7 - OPNsense (via HACS)

Community integration (`travisghansen/hass-opnsense`). Create an API key/secret in OPNsense:
**System -> Access -> Users** -> pick/create a user -> **API keys -> +** (downloads a
`key`/`secret` pair).

1. HACS -> Integrations -> add custom repo `https://github.com/travisghansen/hass-opnsense`
   (type: Integration) -> Download -> restart HA.
2. HA: Add -> **OPNsense** -> URL `https://192.168.10.1`, API key + secret, **Verify SSL: off**.
   Surfaces WAN status, gateway/latency, interface throughput, firewall/CARP.

---

## Step 8 - Speedtest.net

No credential. HA: Add Integration -> **Speedtest.net** -> accept defaults (hourly). Down/up/ping
sensors for the WAN.

---

## Step 9 - Prometheus export (into the existing Grafana)

Push HA's own metrics into the `netframe-monitoring-stack` Prometheus so HA shows up in Grafana.

`configuration.yaml` (edit via the File editor add-on or the SSH add-on, then restart HA):
```yaml
prometheus:
  namespace: hass
```
Create an HA long-lived token: user profile (bottom-left) -> Security -> **Long-lived access
tokens -> Create**. Add a scrape job to Prometheus (repo `machismo0311/netframe-monitoring-stack`):
```yaml
  - job_name: home-assistant
    scrape_interval: 60s
    metrics_path: /api/prometheus
    bearer_token: "<HA long-lived token>"
    static_configs:
      - targets: ["192.168.10.60:8123"]
```
Reload Prometheus. Keep the token in Vaultwarden (not in the git repo - use a secrets file / env).

---

## Step 10 - Enable already-discovered devices

Zero config: Settings -> Devices & Services -> **Discovered** -> add the **Samsung TV**, **Brother
printer** (IPP), and **Xbox** HA already found on the network.

---

## Optional / foundational

- **HA native backups -> Randy:** PBS already image-backs VM 110 nightly (DR is covered). For
  app-level restores, add an NFS export on Randy for `.60` (`/etc/exports`:
  `/datastore/ha-backups 192.168.10.60(rw,sync,no_subtree_check)` then `exportfs -ra`) and in HA
  Settings -> System -> Backups -> add network storage (NFS `192.168.10.187:/datastore/ha-backups`).
- **MQTT (Mosquitto add-on):** foundational for future Zigbee2MQTT / ESPHome / Node-RED. Install
  the Mosquitto broker add-on and create an MQTT user when the first IoT device arrives (see the
  IoT VLAN 40 plan in [[Runbook/Home-Assistant-Install-2026-07-16]]).
- **Advanced SSH & Web Terminal add-on:** gives real SSH into HA (ends the noVNC console dance;
  set a strong password / key). Recommended for manageability.
- **SNMP (EX3400 / APC AP7901 PDU):** possible via the core `snmp` platform (YAML) once SNMP is
  enabled on the device with a read community. The `midatlantic` UPS is already polled by SNMP
  (CyberPower at `192.168.10.180`, community `public`) but is surfaced through NUT (step 4), so no
  separate HA SNMP entry is needed for it.

---

## What was NOT done here (and why)

- Nothing was applied to HA or any prod service - the change-classifier blocks live pushes; this is
  a prep + operator-handoff runbook.
- No secrets are in this file. Tokens/keys are created by the operator and filed in Vaultwarden;
  the NUT password is referenced by its file location on pve3, not copied.
