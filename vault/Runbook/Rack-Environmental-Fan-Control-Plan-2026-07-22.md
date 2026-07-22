# 🌡️ Rack Environmental Monitoring + Thermostatic Fan Control — Plan

**Tags:** #plan #monitoring #thermal #esphome #homeassistant
**Status:** 📋 Planning — NOT ready for deployment (gated on Home Assistant onboarding)
**Date:** 2026-07-22
**Related:** [[Power Distribution]] · [[Rack Layout]] · [[Runbook/Home-Assistant-Install-2026-07-16]] · [[Runbook/Monitoring-Alerting-2026-07-10]]

---

## Goal

Add ambient/inlet **rack temperature sensing** (the lab's only current thermal
visibility is iDRAC/IPMI internal sensors — no ambient inlet/exhaust/room reading,
and the rear panel is removed for R730 depth), then use it to **automatically
switch the top-of-rack exhaust vent fan** on when the rack gets too hot and off
when it cools. Feed the reading into the existing observability stack for
dashboards + Discord alerts.

## Hardware on hand

| Item | Notes |
|---|---|
| **Raspberry Pi Pico W** | RP2040 + WiFi (CYW43439). Confirmed the **W** variant — networking works. Will do **double duty**: environmental sensing **and** front-of-rack lighting (WS2812 via RP2040 PIO) when that's installed. |
| **Adafruit MPL115A2** (PID 992) | I²C barometric pressure + temperature, addr `0x60`. Sitting on the workbench. |

> [!WARNING] MPL115A2 temperature accuracy
> The MPL115A2 is fundamentally a **pressure** sensor; its temperature output
> exists mainly to compensate the pressure reading and is **not factory-calibrated
> as an ambient thermometer** — expect a few degrees offset/drift. **No humidity**,
> so no condensation alerting. Fine for *relative trend + threshold* ("is the rack
> getting hotter?"). For accurate **absolute** temp + humidity, drop in a **BME280
> or SHT31** (STEMMA QT, native ESPHome) later — same 4 wires, one-line YAML swap.

## Architecture

```
Pico W (ESPHome, IoT VLAN 40)
  └─ MPL115A2 (I²C)  → temp + pressure
        │  native ESPHome API
        ▼
Home Assistant (VM 110, pve5, .60)
        │  Prometheus integration
        ▼
Prometheus (CT 103, pve4, .183) → Grafana → Discord alerts
```

- **Platform decision: ESPHome** (not MicroPython). The Pico W's dual role (sensor
  **+** lighting) is the tiebreaker — ESPHome exposes both as native HA entities in
  **one config**; MicroPython would mean hand-rolling both plus MQTT discovery.
- MPL115A2 **is** natively supported: `mpl115a2` platform, added ESPHome 2024.5
  ([PR #6584](https://github.com/esphome/esphome/pull/6584)). Needs a current ESPHome.
- Addressable lighting later uses `rp2040_pio_led_strip` (WS2812 via the Pico's PIO).
  Needs its own **5V supply** + common ground, often a **3.3V→5V level shifter** on data.

### Starter ESPHome config

```yaml
# pico-rack-front.yaml — sensor half now; light block bolts on later
esphome:
  name: pico-rack-front
  friendly_name: Rack Front Sensor
rp2040:
  board: rpipicow
logger:
wifi:
  ssid: !secret iot_wifi_ssid          # VLAN 40 IoT
  password: !secret iot_wifi_password
api:
ota:
  platform: esphome
i2c:
  sda: GP4
  scl: GP5
  scan: true
sensor:
  - platform: mpl115a2
    temperature:
      name: "Rack Inlet Temp"
    pressure:
      name: "Rack Barometric Pressure"
    update_interval: 30s
# --- LIGHTING (add when installed) --------------------------
# light:
#   - platform: rp2040_pio_led_strip
#     name: "Rack Front Lighting"
#     pin: GP2
#     num_leds: 30
#     rgb_order: GRB
#     chipset: ws2812
```

## Thermostatic vent-fan control

Top-of-rack AC exhaust fan on a **switchable smart plug**, driven by the inlet temp.
**Rollout: A then B.**

### Phase A — Home Assistant automation (first)
Sensor (front) → HA automation → smart plug (top). Fast to stand up, easy to tune.
**Caveat: HA-dependent** — HA is a single VM on pve5 (SPOF); if it's down during a
heat event the fan won't switch. Acceptable for initial proving, not for long-term
reliance on a GPU rack.

### Phase B — Autonomous ESPHome (evolve to)
Move control on-device with the `bang_bang` climate controller so it reacts locally,
no HA in the loop. Because the inlet sensor (front) and fan plug (top) are different
devices — and two ESPHome nodes can't talk without HA — true autonomy needs a
**second temp sensor co-located with the fan plug up top** (a ~$10 BME280 on an
ESPHome node up there). Most resilient.

### Failsafe layer (both phases)
A dumb **thermostat outlet** (ThermoCube / Inkbird ITC-308) in parallel — switches
purely on temperature, zero network/software — so a heat event is caught even if HA
**and** ESPHome are down. Cheap insurance for the GPU rack.

> [!IMPORTANT] Two things to get right
> 1. **Hysteresis / dead-band** — never on/off at the same temp or the fan chatters.
>    e.g. **ON at 28°C, OFF at 24°C**. `bang_bang` is built for this (two setpoints);
>    an HA automation needs the dead-band written in by hand.
> 2. **Failsafe = fan ON** — if the sensor/controller drops out, safe-fail is *running*
>    (better to over-cool than cook GPUs).

### Actuator options (pick one)
| Plug | Fit |
|---|---|
| **ESPHome-flashable** (Athom / reflashed Sonoff S31) | Same ecosystem; can run the autonomous Phase-B logic on-device. Preferred for consistency. |
| **Shelly Plug US / Plus Plug** | HA-native + **power monitoring** → detect "commanded ON but drawing 0 W" = fan mechanically dead. |
| **Zigbee plug** | Cheapest, but only if a Zigbee coordinator gets added (none today). |

Put the plug on **IoT VLAN 40**. Do **not** switch mains off a bare Pico GPIO relay —
use a purpose-built plug for mains isolation.

## Alerting tie-in (into existing Grafana → Discord)
The valuable alert isn't "fan turned on" — it's **temp still climbing while the fan
is ON** (fan failed / insufficient): a `RackInletTempHigh + FanRunning` condition →
Discord, alongside the existing `GpuTempHigh` rule. With a Shelly, also alert on
**"fan commanded ON but 0 W"** = mechanical failure.

## Prerequisites / build sequence
1. **Onboard Home Assistant** (VM 110) — create owner account at `http://192.168.10.60:8123`. *Gates everything below.*
2. Install the **ESPHome add-on** in HA.
3. Flash Pico W (USB first, OTA after); wire MPL115A2 (VDD→3V3, GND→GND, SDA→GP4, SCL→GP5).
4. Pico W joins WiFi on **VLAN 40** → auto-discovers into HA.
5. Enable HA **Prometheus integration** → add scrape target on Prometheus (CT 103) → Grafana panel + `RackInletTempHigh` Discord alert.
6. **Phase A** fan automation in HA → validate hysteresis behavior.
7. **Phase B**: add top-of-rack ESPHome node (co-located sensor + plug), migrate control to `bang_bang`, add thermostat-outlet failsafe.

## Open decisions
- [ ] Keep MPL115A2 (free, works now, mediocre temp) vs. order a BME280/SHT31 for accurate temp + humidity/condensation.
- [ ] Smart-plug choice (ESPHome-flashable vs Shelly).
- [ ] ON/OFF setpoints + dead-band (draft: 28°C / 24°C — tune against real rack readings).
- [ ] Whether to add the standalone thermostat-outlet failsafe from day one.

## See also
- Companion power-safety item: **NUT graceful shutdown** (UPS auto-shutdown is
  currently unwired — alerts fire but nothing powers down on battery). To be captured
  as its own plan. Ref [[Power Distribution]] and [[High Availability/High Availability MOC]].
