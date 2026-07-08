# Jarvis LLM Inference Platform — Build & Operations Runbook

**Node:** Jarvis (Dell PowerEdge R730, service tag DWG7HH2)
**Status:** 🟢 In production
**Built:** 2026-07-04 → 2026-07-05
**Author:** Kyle Mason (NetFRAME homelab)
**Related:** [[Compute/Dell R730 - General Node]] · [[Compute/Dell R730 - ML Node]] · [[Infrastructure/Services & VMs]] · [[Runbook/VLAN30-Migration-Report-2026-07-02]]

---

## 1. Executive summary

Jarvis was commissioned as the homelab's **LLM inference platform**: two NVIDIA Quadro RTX 6000 GPUs serving Qwen2.5 72B via Ollama, fronted by a custom OpenAI-compatible router (`llm_router`) with retrieval-augmented generation (RAG) over the Home-Lab documentation, and a ChatGPT-style web front-end (Open WebUI). Supporting work covered GPU driver bring-up, a bespoke GPU-aware fan-control daemon, a dedicated 10 GbE storage path, reverse-proxy/DNS integration, and backup protection.

Everything runs **on-premises** — no data leaves the LAN unless the optional Claude API fallback is explicitly enabled.

**Access:** `http://chat.netframe.local` (web UI) · `http://llm.netframe.local` (API).

---

## 2. Architecture

```
                 Browser / OpenAI clients (LAN, Pi-hole DNS)
                          │
                          ▼
        ┌──────────────── NPM (LXC 101, pve3 .181) ────────────────┐
        │   chat.netframe.local ─┐          llm.netframe.local ─┐   │
        └────────────────────────┼────────────────────────────┼───┘
                                 ▼                             ▼
                   Open WebUI (LXC 107, pve3 .185:8080)       │
                                 │  OpenAI API                │
                                 └──────────────┬─────────────┘
                                                ▼
                              llm_router (Jarvis .31:8000, systemd)
                       ┌───────────────┬────────────────┬──────────────┐
                       ▼               ▼                ▼              ▼
                 model="local"    model="rag"     escalate/claude-*   (fallback)
                       │               │                │
                       ▼               ▼                ▼
                 Ollama qwen2.5:72b   RAG index      Anthropic API
                 (2× RTX 6000)     (nomic-embed +   (claude-opus-4-8,
                                    numpy cosine)     if key set)
```

- **Management/corosync:** onboard 1 GbE, VLAN 1 (`192.168.10.31`).
- **Storage/PBS/egress:** ConnectX-3 10 GbE, VLAN 30 (`192.168.30.31`, EX3400 `xe-0/2/2`).
- **iDRAC:** VLAN 20 (`192.168.20.21`).

---

## 3. Hardware

| Component | Detail |
|---|---|
| Chassis | Dell PowerEdge R730, 2× Xeon E5-2687W v4, 384 GB LRDIMM |
| GPUs | **2× NVIDIA Quadro RTX 6000, 24 GB each / 48 GB total** (Turing TU102), PCI `03:00.0` + `82:00.0`, driver 550.163.01 |
| NIC (mgmt) | 4× Broadcom BCM57800 1/10 G onboard (nic2 → vmbr0, VLAN 1) |
| NIC (10 G) | Mellanox ConnectX-3 (`enp132s0` → vmbr1, VLAN 30 via EX3400 `xe-0/2/2`) |
| Kernel | 6.14.11-9-pve (GRUB-pinned for NVIDIA 550 — **do not upgrade**) |

**Install note — nouveau conflict:** on first boot with GPUs present, the open-source `nouveau` driver claimed both cards (the proprietary driver had been staged pre-install and never blacklisted), so `nvidia-smi` reported "No devices probed." Fixed with `/etc/modprobe.d/blacklist-nouveau.conf` + `update-initramfs -u` + reboot.

### 3.1 Local storage (ZFS) — added 2026-07-08

Six drives hang off the onboard **LSI/Broadcom SAS-3 3008 (HBA330, IT mode)** — all pass through raw, so ZFS owns them directly (no `storcli`, same as Randy's data HBA).

| Pool | Layout | Devices | Usable | Mount | Tuning | Purpose |
|---|---|---|---|---|---|---|
| `tank` | raidz1 (5-wide) | 5× 2 TB HDD (ST2000NX046x, `sdd`–`sdh`) | **7.2 TB** | `/tank` | ashift=12, lz4, atime=off, recordsize=1M | Model library + bulk/datasets |
| `scratch` | single disk | 1× 200 GB SSD (ST200FM0053, `sdc`) | **181 GB** | `/scratch` | ashift=12, lz4, atime=off | Fast scratch / hot tier |

- Pools built on `/dev/disk/by-id` (stable across bay/enumeration changes); PVE auto-imports via the `zfs-import` services. `tank` survives any single HDD failure; `scratch` is single-disk (no redundancy — scratch only).
- **OS/boot untouched:** Proxmox root is on the internal IDSDM SD module (`sdb`) + the 200 GB SSD in bay 0 (`sda`, `pve` VG). A two-way SSD mirror isn't available because bay 0 is the OS disk, so only the *second* 200 GB SSD (`sdc`) is free — hence `scratch` is single-disk.
- **Ollama models moved to ZFS (2026-07-08):** `OLLAMA_MODELS` was repointed from the 100 G `pve/models` ext4 LV to a dedicated **`tank/models`** dataset (`/tank/models`), giving the model library ~7 TB of headroom instead of 100 G. Set in the systemd drop-in **`/etc/systemd/system/ollama.service.d/override.conf`** (⚠️ a *pre-existing* `override.conf` already set `/opt/models`; drop-ins load alphabetically so a new higher-sorting file is silently overridden — edit `override.conf` itself). Verified: `ollama list` shows all 3 models and a cold-load completion from `/tank` returns in ~6 s. The old 100 G `pve/models` LV was kept briefly as a rollback, then **reclaimed the same day** once the move was verified — its fstab line was removed (backup `/etc/fstab.bak-preremove-models-20260708`, `mount -a` clean) and the LV `lvremove`d, returning ~100 G to the `pve` VG (VFree 36 G → 136 G).

---

## 4. Software stack

| Layer | What | Where |
|---|---|---|
| Inference | Ollama v0.31.1, models `qwen2.5:72b` (~47 GB) + `nomic-embed-text` (embeddings) | Jarvis host, `/opt/models` (98 G LV) |
| Router | `llm_router` (FastAPI, OpenAI-compatible) | Jarvis, systemd `llm_router.service` `:8000`, `/opt/llm_router` |
| RAG | numpy cosine index over the Home-Lab vault (418 chunks) | Jarvis, `/opt/llm_router/rag_*.{npy,json}` |
| Web UI | Open WebUI v0.10.2 (native pip) | pve3 **LXC 107** (`.185:8080`), systemd `open-webui.service` |

**Router routing logic** (`model` field in the request):
- `local` (or any non-special value) → Ollama `qwen2.5:72b`.
- `rag` → embed query → retrieve top-K vault chunks → ground the local model → answer with `[source]` citations.
- `claude-*` or `"escalate": true` → Anthropic API (`claude-opus-4-8`, adaptive thinking) — **only if `ANTHROPIC_API_KEY` is set** in `/etc/llm_router.env`; otherwise returns 503.
- Ollama failure → auto-fallback to Claude (if enabled).

> Design note: the original spec called for logprob-confidence routing, but Ollama exposes no per-token logprobs, so escalation is by flag/model/failure. Streaming is not yet implemented (responses are non-streamed).

**VRAM constraint:** the Q4 72B (~47 GB) barely fits 48 GB VRAM, leaving little room for the KV cache. The router caps the local context (`OLLAMA_NUM_CTX=8192`, via Ollama's native `/api/chat`) to keep it mostly on GPU; it still spills ~7 % to CPU. Drop to `4096` for fully-GPU-resident, or point `LOCAL_MODEL` at a 32 B for a faster/roomier assistant.

Source of truth for the router + RAG code: **`Home-Lab/scripts/llm_router/`** (`llm_router.py`, `rag_ingest.py`, `requirements.txt`, unit + env example, README).

---

## 5. Networking

| Name | DNS | Front | Backend |
|---|---|---|---|
| `llm.netframe.local` | Pi-hole → .181 | NPM host id 5 (HTTP) | Jarvis `.31:8000` (router) |
| `chat.netframe.local` | Pi-hole → .181 | NPM host id 6 (HTTP) | LXC 107 `.185:8080` (Open WebUI) |

- **`netframe.local` is internal-only** — records live in **Pi-hole v6** local DNS (not Cloudflare). They resolve for any client using Pi-hole (`192.168.10.177`) as its resolver.
- **NPM admin** (`:81`) is firewalled to Ares `.199` (F-05); manage it by binding `curl --interface 192.168.10.199`. Login `kyle@kylemason.org`.
- **Ares DNS** was repointed to Pi-hole (`.177` primary, `1.1.1.1` fallback) on 2026-07-05 so `*.netframe.local` resolves from the workstation too (was pinned immutable to public DNS; backup at `/etc/resolv.conf.bak`).
- **10 GbE storage path:** Jarvis VLAN 30 (NFS/PBS/egress) moved off the onboard 1 G onto the ConnectX-3 — EX3400 `xe-0/2/2` = access VLAN 30, Jarvis `vmbr1`/`enp132s0` = `192.168.30.31`. Mgmt/corosync stay on the 1 G.

---

## 6. Thermal / fan management

iDRAC cannot read a third-party GPU's temperature, so its only native options are a loud fixed ramp or a quiet floor that never responds to GPU heat. On install, the default `ThirdPartyPCIFanResponse=Enabled` pinned all fans to **~14,800 RPM at idle**.

**Solution — `gpu-fan-control` daemon** (`Home-Lab/scripts/gpu-fan-control.{sh,service}`, installed `/usr/local/sbin/` + systemd):
- Closed-loop: reads max GPU temp via `nvidia-smi` every 5 s, sets fan % via iDRAC manual control (`ipmitool raw 0x30 0x30`). Curve: 15 % idle (~4,080 RPM) → up to 100 %.
- Chassis safety net: exhaust ≥ 45 °C forces ≥ 70 %.
- **Failsafe:** any stop/crash/read-failure hands fans back to iDRAC auto (a *measured-safe* baseline); self-asserts `ThirdPartyPCIFanResponse=Disabled` at startup, so it survives reboots.
- Verified across a reboot; measured GPU load stays ≤ 63 °C on the real 72 B workload.

Full investigation: [[Compute/Dell R730 - ML Node]] → Thermal / Fan Control.

---

## 7. Access & usage

### Web UI (recommended)
1. Browse to **`http://chat.netframe.local`** (any Pi-hole-DNS client on the LAN).
2. First visit creates the local admin account.
3. Pick a model from the dropdown: **`qwen2.5:72b`** (plain) or **`rag`** (grounded on the vault, with citations).

### API (OpenAI-compatible)
```bash
curl http://llm.netframe.local/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"rag","messages":[{"role":"user","content":"which node runs Wazuh?"}]}'
```
Point any OpenAI client at `http://llm.netframe.local/v1` (any `api_key` string).

> First request after idle takes ~40 s while the 72 B cold-loads ~47 GB into the GPUs; fast while resident (~5 min keep-alive).

---

## 8. Operations

**Service management** (Jarvis): `systemctl {status|restart} llm_router gpu-fan-control`
**Service management** (LXC 107): `pct exec 107 -- systemctl {status|restart} open-webui`

**Re-index RAG** (after vault docs change), from Ares:
```bash
rsync -a --prune-empty-dirs --exclude=.git --exclude=dotfiles \
  --exclude='*CLAUDE.netframe.md' --exclude='*CLAUDE.dotfiles.md' \
  --include='*/' --include='*.md' --exclude='*' \
  ~/Home-Lab/ jarvis:/opt/llm_router/rag_docs/
ssh jarvis 'cd /opt/llm_router && venv/bin/python rag_ingest.py && systemctl restart llm_router'
```

**Enable the Claude fallback:** add `ANTHROPIC_API_KEY=sk-ant-...` to Jarvis `/etc/llm_router.env`, then `systemctl restart llm_router`. `claude-opus-4-8` then appears as a model; `/health` reports `claude_enabled: true`.

---

## 9. Backup & recovery

> ⚠️ **Cluster-wide backup outage found & fixed 2026-07-06.** During this work it was discovered that **no pve3 backup had succeeded since 2026-07-02** — the VLAN 30 migration repointed the PBS storage to Randy's VLAN 30 address (`192.168.30.187`), but the VLAN-1-only pve nodes route to it *via a bogus gateway (`192.168.1.1`)*: small pings pass, but **bulk PBS uploads stall at 0 B and reset after ~13 min**. **Fix:** the `randy-pbs` storage was repointed to Randy's dual-homed **VLAN 1** IP **`192.168.10.187`** (directly reachable on `vmbr0` by every node). Immediate backups then completed in seconds.

**10 G backup path for VLAN-30 nodes (2026-07-08):** to keep the fast path for the nodes that *can* use it, a second storage **`randy-pbs-10g`** was added → server **`192.168.30.187`** (same datastore/fingerprint), **restricted to `nodes QuarkyLab,Jarvis,Randy`** (which reach `.30.187` directly on `vmbr0.30` at 10 Gb/s — verified). The VM backup job was split: **VM 100 (OPNsense, pve2)** stays on `randy-pbs` (VLAN 1), while **VM 104 (Wazuh, QuarkyLab)** moved to its own job on `randy-pbs-10g` (VLAN 30, 10 G — verified 17 s). Both storages target the **same PBS datastore**, so chunks dedup across paths. `pbs-workspace-backup.sh` and the `/data` NFS mount also use `.30.187` and only matter on the GPU nodes.

- **Datastores (same PBS, two paths):** `randy-pbs` → `192.168.10.187:8007` (VLAN 1, all nodes); `randy-pbs-10g` → `192.168.30.187:8007` (VLAN 30, 10 G, nodes QuarkyLab/Jarvis/Randy only). ZFS ~23 T usable.
- **Backup jobs:** (1) LXC 101/102/103/105/106/107 → `randy-pbs`, 02:00; (2) VM 100 (OPNsense) → `randy-pbs`, 03:00; (3) VM 104 (Wazuh) → `randy-pbs-10g`, 03:00 (10 G).
- **Nightly LXC job** (`jobs.cfg` id `4ed4c3e5…`, 02:00, zstd, keep-daily=7/keep-weekly=4) now covers **LXC 101, 102, 103, 105, 106, 107**. (CT 106 = homepage and CT 107 = Open WebUI were added 2026-07-05; 106 had never been backed up.)
- **Immediate backups** of CT 106 and 107 succeeded 2026-07-06 (`ct/106/…15:16Z` 1.8 GB, `ct/107/…15:16Z` 12.7 GB).
- **Restore:** PBS UI → `randy-pbs` → select the CT snapshot → Restore to pve3 (or `pct restore <id> <volid> --storage local-lvm`).
- The Jarvis host itself is not a PBS guest; its config (router, daemon, env) is version-controlled in `Home-Lab/scripts/` and reproducible from this runbook.

---

## 10. Verification (2026-07-05)

| Check | Result |
|---|---|
| GPUs bound under nvidia | ✅ 2× RTX 6000, 550.163.01, both `Kernel driver in use: nvidia` |
| gpu-fan-control at boot | ✅ active/enabled; idle ~4,080 RPM; failsafe verified |
| 10 GbE VLAN 30 | ✅ 10000 Mb/s, PBS `.30.187` reachable, cluster 7/7 quorate |
| llm_router local | ✅ real completion from qwen2.5:72b |
| RAG | ✅ grounded answer with `[source]` citations (418-chunk index) |
| llm.netframe.local (NPM) | ✅ `/health`, `/v1/models` via proxy |
| Open WebUI | ✅ `http://chat.netframe.local` 200 by hostname; backend sees router models |
| PBS backup 106/107 | ✅ 2026-07-06 — both snapshots persisted (106 1.8 GB / 107 12.7 GB) after repointing `randy-pbs` to `.10.187` (fixed a cluster-wide outage since 07-02) |
| Nightly LXC job coverage | ✅ `vmid 101,102,103,105,106,107`; 07-07 & 07-08 nightlies all `TASK OK` |
| VM 104 over 10 G VLAN 30 | ✅ 2026-07-08 — `randy-pbs-10g` (.30.187), backed up in 17 s; QuarkyLab reaches .30.187 direct on vmbr0.30 @ 10 Gb/s |

---

## 11. Known limitations / future work

- [ ] **Claude fallback** disabled until `ANTHROPIC_API_KEY` is set.
- [ ] **Streaming** not implemented in `llm_router` (non-streamed responses).
- [ ] **RAG re-index is manual** — a nightly systemd timer could auto-refresh.
- [ ] **VRAM-bound** on the 72 B (minor CPU spill); a 32 B would be faster with more context headroom.
- [ ] **ErrPrompt / F1 POST-halt** on Jarvis iDRAC still pending (iDRAC job queue stuck on fw 2.86).
- [ ] **TLS** — all `netframe.local` fronts are HTTP-only; step-ca could issue internal certs.

---

## 12. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `nvidia-smi` "No devices probed" | nouveau grabbed the cards → ensure `blacklist-nouveau.conf` + rebuild initramfs |
| Fans at ~14,800 RPM idle | `gpu-fan-control` not running → `systemctl start gpu-fan-control` (it disables the third-party response) |
| Ollama embeddings 500 during ingest | VRAM race (72 B resident) or an oversized chunk → `ollama stop qwen2.5:72b`; chunker hard-caps chunk size |
| 72 B very slow / partly on CPU | context too large → keep `OLLAMA_NUM_CTX≤8192` (router already does this) |
| `*.netframe.local` won't resolve | client isn't using Pi-hole DNS → point resolver at `192.168.10.177` |
| NPM `:81` refuses admin API | firewalled to `.199` → `curl --interface 192.168.10.199` |

---

## 13. Change log

- **2026-07-04** — 2× RTX 6000 installed & verified; nouveau blacklisted; ConnectX-3 added; `gpu-fan-control` daemon built/deployed; `llm_router` built + activated; fronted at `llm.netframe.local` (NPM + Pi-hole).
- **2026-07-05** — VLAN 30 moved onto the 10 GbE ConnectX; RAG over the vault added to `llm_router`; Ares DNS repointed to Pi-hole; Open WebUI deployed (LXC 107) at `chat.netframe.local`.
- **2026-07-06** — CT 106 + 107 added to the nightly PBS LXC job; **discovered pve3 backups had been failing since the 07-02 VLAN 30 migration** (PBS at `.30.187` unreachable for bulk transfer from VLAN-1 nodes) and **fixed it** by repointing `randy-pbs` to Randy's VLAN 1 IP `.10.187`; immediate backups of 106 + 107 succeeded.
- **2026-07-08** — confirmed 07-07/07-08 nightlies healthy; added the **10 G backup path**: new `randy-pbs-10g` storage (→ `.30.187`, nodes QuarkyLab/Jarvis/Randy) and split VM 104 (Wazuh) onto it so it backs up over the 10 G VLAN 30 link (verified 17 s). pve-node/VLAN-1 backups stay on `randy-pbs` (.10.187).
- **2026-07-08** — **local ZFS storage added** (new drives): 5× 2 TB HDD → `tank` (raidz1, 7.2 TB, `/tank`) + free 200 GB SSD → `scratch` (`/scratch`), both by-id on the HBA330 IT-mode controller (§3.1). **Migrated the Ollama model store** off the 100 G `pve/models` LV onto the `tank/models` dataset (repointed `OLLAMA_MODELS` in ollama's systemd `override.conf`); verified `ollama list` + a cold-load inference from `/tank` (~6 s), then **reclaimed the old LV** (fstab line removed, `lvremove` — ~100 G back to the `pve` VG).
