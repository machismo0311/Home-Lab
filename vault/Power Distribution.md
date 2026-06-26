# ⚡ Power Distribution
**Tags:** #infrastructure #power #ups  
**Related:** [[Rack Layout]] · [[Compute/Dell R730 - ML Node]] · [[00 - Homelab MOC]]

---

## UPS Strategy — Split Bus Architecture

Two independent UPS units cover separate load zones, protecting different tiers of equipment based on criticality and power draw.

```mermaid
flowchart TB
    WALL[🔌 Wall Circuit / PDU] --> FURMAN[Furman RP-8\nPower Conditioner\nU6]

    FURMAN --> UPSA
    FURMAN --> UPSB

    subgraph UPSA_ZONE["UPS A — Top Half Bus"]
        UPSA[Tripp Lite SMART1500VA\n1500VA / ~900W\nU4–U5]
        UPSA --> EX3400[Juniper EX3400-48P]
        UPSA --> USW[UniFi USW-24-250W]
        UPSA --> EX2300[Juniper EX2300-48P]
        UPSA --> PATCH[Patch Panels]
        UPSA --> G4A[EliteDesk G4 SFF A]
        UPSA --> G4B[EliteDesk G4 SFF B]
        UPSA --> G3A[EliteDesk G3 Mini A]
        UPSA --> G3B[EliteDesk G3 Mini B]
        UPSA --> MACPI[Mac mini + RPi 4]
    end

    subgraph UPSB_ZONE["UPS B — Bottom Half / ML Bus"]
        UPSB[Middle Atlantic UPS-2200R\n2200VA / ~1320W\nU1–U2]
        UPSB --> R730ML[Dell R730 ML Node\n⚠️ HIGH DRAW]
        UPSB --> R730GEN[Dell R730 General]
        UPSB --> SM[SuperMicro CSE-219U]
        UPSB --> DS4246[NetApp DS4246]
    end

    style R730ML fill:#ff4444,color:#fff
    style UPSB fill:#1a1a2e,color:#eee
    style UPSA fill:#162447,color:#eee
```

---

## UPS Specs

### Tripp Lite SMART1500VA (UPS A — Top Half)
| Field | Value |
|---|---|
| Model | SMART1500LCD |
| Capacity | 1500VA / 900W |
| Rack Position | U4–U5 (2U) |
| Form Factor | 2U rackmount |
| Runtime (half load) | ~15–20 min est. |
| Bus Assignment | Networking + Small compute |
| Output | 8 outlets (battery + surge) |

### Middle Atlantic UPS-2200R (UPS B — Bottom / ML Bus)
| Field | Value |
|---|---|
| Model | UPS-2200R |
| Capacity | 2200VA / 1320W |
| Rack Position | U1–U2 (2U) |
| Form Factor | 2U rackmount |
| Runtime (half load) | ~10–15 min est. |
| Bus Assignment | Heavy compute + Storage |
| Role | Rack bottom anchor + ML power bus |
| Notes | Arrived to anchor the bottom of the rack |

---

## Load Estimates

> [!NOTE]
> These are rough estimates. Actual draw varies with workload. Meter each PDU circuit to validate.

| Device | Est. Draw (W) | UPS |
|---|---|---|
| Juniper EX3400-48P | ~150W | A |
| UniFi USW-24-250W | ~60W | A |
| Juniper EX2300-48P | ~80W | A |
| HP EliteDesk G4 SFF ×2 | ~130W | A |
| HP EliteDesk G3 Mini ×2 | ~80W | A |
| Mac mini + RPi 4 | ~30W | A |
| **UPS A Total Est.** | **~530W** | — |
| Dell R730 ML Node (idle) | ~200W | B |
| Dell R730 ML Node (CUDA load) | ~500W+ | B |
| Dell R730 General (idle) | ~150W | B |
| SuperMicro CSE-219U (idle) | ~120W | B |
| NetApp DS4246 | ~60W | B |
| **UPS B Total Est. (idle)** | **~530W** | — |
| **UPS B Total Est. (ML load)** | **~830W+** | — |

> [!WARNING] CUDA Load
> The RTX 6000 under full CUDA load can pull 250W by itself. Fernanda's ML workloads may push UPS B well above 1000W. Monitor via iDRAC and UPS display. UPS-2200R rated at 1320W continuous — should be fine, but watch it.

---

## Furman RP-8

- **Role:** Power conditioning / noise filtering upstream of both UPS units
- **Position:** U6
- **Outlets:** 8 total (rear-mount)
- **Features:** Surge protection, EMI/RFI filtering, voltmeter

---

## 🔋 UPS Monitoring (Live — 2026-06-26)

NUT (Network UPS Tools 2.8.1) runs on the **pve3 host** as a network server (`MODE=netserver`),
exposing both UPS units on TCP 3493. Homepage (LXC 106) shows live `peanut` widgets for each in a
"Power & UPS" group (Middle Atlantic = UPS A, Tripp Lite = UPS B).

| UPS | NUT name | Driver | Connection |
|---|---|---|---|
| Tripp Lite SMART1500 | `tripplite` | `usbhid-ups` | USB → pve3 (`09ae:2012`) |
| Middle Atlantic UPS-OL2200R | `midatlantic` | `snmp-ups` (`mibs=cyberpower`) | SNMP card `192.168.10.180`, RFC1628 UPS-MIB, enterprise OID 3808 = CyberPower (Mid-Atlantic rebrands CyberPower OL) |

- **upsd** listens on `127.0.0.1:3493` + `192.168.10.201:3493` (anonymous read).
- **upsmon** monitors both locally (`monuser`, primary role) — logging only, no auto-shutdown wired yet.
- Config lives in `/etc/nut/{nut,ups,upsd,upsd.users,upsmon}.conf` on pve3. monuser password is **not** in git.
- Boot-enabled services: `nut-server`, `nut-monitor`, `nut-driver@tripplite`, `nut-driver@midatlantic`.
- **PeaNUT** (`brandawg93/peanut`, container in LXC 106 `docker-compose.yml`, port `8081→8080`) bridges
  `upsd` → the REST API that Homepage's `peanut` widget consumes (Basic Auth, user `homepage`; creds **not** in git).
  Homepage v1.13 has no direct `nut` widget — it integrates NUT only via PeaNUT. PeaNUT also serves its own UPS dashboard.
- Homepage `peanut` widgets show battery %, load %, and status. See [[Runbook/Homepage-Setup-2026-06-26]].

### Still planned
| Tool | Target |
|---|---|
| Grafana dashboard | UPS load %, runtime remaining (scrape NUT via a prometheus nut-exporter) |
| Alerting | upsmon `NOTIFYCMD` / Uptime Kuma → notify on battery event |
