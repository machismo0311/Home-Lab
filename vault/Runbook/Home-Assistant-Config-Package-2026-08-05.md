# Home Assistant Copy-Paste Config Package (2026-08-05)

**Tags:** #runbook #homeassistant #config
**Related:** [[Runbook/Home-Assistant-Integrations-2026-08-05]]

Paste-ready YAML for VM 110 once the integrations from
[[Runbook/Home-Assistant-Integrations-2026-08-05]] are added. Nothing here touches the live box on
its own - apply via the **File editor** or **Advanced SSH & Web Terminal** add-on, then restart HA.

> **Entity-ID caveat:** the dashboard/automations below use the *conventional* entity_ids these
> integrations produce. HA slugifies from device names, so after adding each integration, open
> **Developer Tools -> States**, confirm the real IDs, and adjust. Every predicted ID is flagged
> with `# verify`.

---

## 1. `configuration.yaml` additions

Append to `/config/configuration.yaml` (keep your existing `default_config:` etc.):

```yaml
# --- Prometheus metrics export -> existing Grafana (integration step 9) ---
prometheus:
  namespace: hass

# --- Recorder: 30-day history, trim the noisiest churn (optional tidy) ---
recorder:
  purge_keep_days: 30
  exclude:
    entity_globs:
      - sensor.speedtest_*        # only meaningful hourly; no need for high-res history
```

**Notifier for the automations below.** Pick one so `notify` works:

- *Easiest:* install the **Home Assistant Companion** app on your phone -> it auto-creates
  `notify.mobile_app_<device>`. Swap that into the automations.
- *Reuse your Discord pattern:* add a REST notifier (webhook URL goes in `secrets.yaml`, never here):

```yaml
# configuration.yaml
notify:
  - name: discord_ha
    platform: rest
    resource: !secret discord_ha_webhook
    method: POST_JSON
    data_template:
      content: "{{ message }}"
```
```yaml
# secrets.yaml
discord_ha_webhook: "https://discord.com/api/webhooks/XXXX/YYYY"
```

---

## 2. Automations

Add via **Settings -> Automations -> ... -> Edit in YAML**, or drop into `automations.yaml`.
Replace `notify.discord_ha` with your chosen notifier.

```yaml
- alias: "UPS - on battery (power lost)"
  id: ha_ups_on_battery
  trigger:
    - platform: state
      entity_id: sensor.tripplite_status          # verify (NUT ups.status)
      to: "OB"                                     # On Battery
    - platform: state
      entity_id: sensor.midatlantic_status         # verify
      to: "OB"
  action:
    - service: notify.discord_ha
      data:
        message: >
          ⚡ UPS on battery: {{ trigger.entity_id }} lost mains power at
          {{ now().strftime('%H:%M') }}.

- alias: "UPS - low runtime (critical)"
  id: ha_ups_low_runtime
  trigger:
    - platform: numeric_state
      entity_id: sensor.midatlantic_battery_runtime # verify (seconds)
      below: 300                                    # < 5 min left
  action:
    - service: notify.discord_ha
      data:
        message: >
          🔋 CRITICAL: {{ trigger.entity_id }} runtime under 5 min - begin graceful shutdowns.

- alias: "Proxmox - node down"
  id: ha_pve_node_down
  trigger:
    - platform: state
      entity_id:
        - binary_sensor.pve2_status                # verify (Proxmox VE integration)
        - binary_sensor.pve3_status
        - binary_sensor.pve4_status
        - binary_sensor.pve5_status
        - binary_sensor.quarkylab_status
        - binary_sensor.jarvis_status
        - binary_sensor.randy_status
      to: "off"
      for: "00:02:00"
  action:
    - service: notify.discord_ha
      data:
        message: "🖥️ Proxmox node offline > 2 min: {{ trigger.entity_id }}"

- alias: "Printer - low ink/toner"
  id: ha_printer_low
  trigger:
    - platform: numeric_state
      entity_id: sensor.brother_black_toner_remaining # verify
      below: 10
  action:
    - service: notify.discord_ha
      data:
        message: "🖨️ Brother printer toner low ({{ states(trigger.entity_id) }}%)."
```

> These deliberately overlap little with the existing Grafana->Discord infra alerts: HA is the
> place for physical/room signals (power lost, printer) and phone push. If you don't want double
> alerts on node-down, drop the "Proxmox - node down" block (Grafana already covers InstanceDown).

---

## 3. NetFRAME Lovelace dashboard

**Settings -> Dashboards -> + New dashboard** (or edit one) -> top-right **... -> Edit dashboard ->
... -> Raw configuration editor** -> paste. Delete rows whose integration you haven't added yet.

```yaml
title: NetFRAME
views:
  - title: Overview
    path: overview
    icon: mdi:server-network
    cards:
      - type: markdown
        content: "## NetFRAME Homelab — live"
      - type: horizontal-stack
        cards:
          - type: entity
            name: WAN Down
            entity: sensor.speedtest_download        # verify
          - type: entity
            name: WAN Up
            entity: sensor.speedtest_upload          # verify
          - type: entity
            name: Ping
            entity: sensor.speedtest_ping            # verify
      - type: glance
        title: Cluster nodes
        entities:
          - binary_sensor.pve2_status                # verify (all 7 below)
          - binary_sensor.pve3_status
          - binary_sensor.pve4_status
          - binary_sensor.pve5_status
          - binary_sensor.quarkylab_status
          - binary_sensor.jarvis_status
          - binary_sensor.randy_status

  - title: Power / UPS
    path: power
    icon: mdi:battery-charging
    cards:
      - type: gauge
        name: Tripp Lite battery
        entity: sensor.tripplite_battery_charge      # verify
        min: 0
        max: 100
      - type: entities
        title: Tripp Lite (UPS A)
        entities:
          - sensor.tripplite_status                  # verify
          - sensor.tripplite_load
          - sensor.tripplite_battery_runtime
          - sensor.tripplite_input_voltage
      - type: gauge
        name: Middle Atlantic battery
        entity: sensor.midatlantic_battery_charge    # verify
        min: 0
        max: 100
      - type: entities
        title: Middle Atlantic (UPS B)
        entities:
          - sensor.midatlantic_status                # verify
          - sensor.midatlantic_load
          - sensor.midatlantic_battery_runtime

  - title: Network
    path: network
    icon: mdi:lan
    cards:
      - type: entities
        title: Pi-hole (HA pair)
        entities:
          - switch.pi_hole                           # verify (primary .177)
          - sensor.pi_hole_ads_blocked_today
          - sensor.pi_hole_dns_queries_today
          - sensor.pi_hole_ads_percentage_blocked_today
          - switch.pi_hole_2                         # verify (secondary .178)
      - type: entities
        title: OPNsense / WAN
        entities:
          - sensor.opnsense_wan_status               # verify (OPNsense HACS integration)
          - sensor.opnsense_gateway_wan_delay        # verify

  - title: Media / AI
    path: media
    icon: mdi:play-network
    cards:
      - type: entities
        title: Jellyfin
        entities:
          - sensor.jellyfin_movies                   # verify (library counts vary)
          - sensor.jellyfin_tv_shows
      - type: markdown
        content: >
          ### Assist (local AI)
          Ask the Assist chat (top-left) - backed by Jarvis llm_router, model `rag`
          (vault-grounded) or `qwen2.5:72b`.
```

---

## 4. Grafana side (Prometheus scrape)

After `prometheus:` is live in `configuration.yaml` and you've minted an HA **long-lived access
token** (profile -> Security), add this job to the `netframe-monitoring-stack` Prometheus config
and reload. Keep the token in a secrets file / env, not committed.

```yaml
  - job_name: home-assistant
    scrape_interval: 60s
    metrics_path: /api/prometheus
    bearer_token: "<HA long-lived token>"
    static_configs:
      - targets: ["192.168.10.60:8123"]
        labels:
          instance: homeassistant
```

> I did not open a PR for this yet because it needs the HA token first (which requires HA running
> the export). Say the word once the token exists and I'll stage the branch/PR against
> `machismo0311/netframe-monitoring-stack`.

---

## Apply checklist

1. Integrations added (see [[Runbook/Home-Assistant-Integrations-2026-08-05]]).
2. Paste section 1 into `configuration.yaml` (+ `secrets.yaml` if using Discord). **Check config**
   (Developer Tools -> YAML -> Check configuration) then **Restart HA**.
3. Reconcile predicted entity_ids (`# verify`) against Developer Tools -> States.
4. Paste sections 2 (automations) and 3 (dashboard).
5. Enable the Prometheus job (section 4) once the token exists.
