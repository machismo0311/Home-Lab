# DNS local-records gap + Operations Console publication - 2026-07-15

**Tags:** #runbook #dns #pihole #npm #reverse-proxy #jarvis #netframe-monitor #dr
**Related:** [[Runbook/DNS-HA-OPNsense-Resilience-2026-07-10]] · [[Runbook/Jarvis-LLM-Platform-2026-07-05]] · [[Runbook/Homepage-Setup-2026-06-26]] · [[Infrastructure/Services & VMs]]

Publishing `console.kylemason.org` surfaced a pre-existing DNS gap that had silently broken three services LAN-wide. The gap is documented first because it is the more important finding.

---

## 1. The gap: three services unresolvable for every LAN client ⚠️ FIXED

**Symptom:** `vault.kylemason.org`, `grafana.kylemason.org` and `wazuh.kylemason.org` would not load from any LAN device. The services themselves were healthy the entire time. This was purely DNS.

**How to recognise it:**

```
dig +short @1.1.1.1 vault.kylemason.org          -> 192.168.10.181   (fine)
dig +short @192.168.10.177 vault.kylemason.org   -> (empty)          (broken)
dig @192.168.10.177 vault.kylemason.org | grep status  -> NOERROR
```

NOERROR with an **empty answer** is the tell. Not NXDOMAIN, not SERVFAIL. `curl` reports HTTP 000 and a browser just says it cannot connect.

**Cause:** the split-horizon rebind gotcha, already documented in [[Runbook/DNS-HA-OPNsense-Resilience-2026-07-10]]. Every `*.kylemason.org` name has a **public Cloudflare A record (DNS-only / grey cloud) pointing at the private NPM IP `192.168.10.181`**. Pi-hole/dnsmasq DNS-rebind protection drops upstream answers containing RFC1918 addresses, so the name resolves for anything using a public resolver and returns nothing for anything using Pi-hole. An explicit Pi-hole **local DNS record** bypasses the protection.

**Why it went unnoticed:** OPNsense DHCP hands out `.177` + `.178` on all 7 VLAN scopes, so *every* LAN client is a Pi-hole client. The records were only ever added for names someone actively used from a Pi-hole client (`homepage`, `health`). Ares itself was pinned to public DNS until 2026-07-05, which masked the gap while these hosts were being built. Audit of `dns.hosts` on 2026-07-15 found:

| Name | Local record before | Status |
|---|---|---|
| `homepage.kylemason.org` | present | was working |
| `health.kylemason.org` | present (added 2026-07-15) | was working |
| `vault.kylemason.org` | **missing** | broken LAN-wide |
| `grafana.kylemason.org` | **missing** | broken LAN-wide |
| `wazuh.kylemason.org` | **missing** | broken LAN-wide |
| `console.kylemason.org` | **missing** (new) | added in this change |

**The DR trap.** `vault.kylemason.org` being in that list is the serious part:

1. Vaultwarden is unreachable by name, so the `bw` CLI silently stops syncing. It had last synced 2026-07-14.
2. The documented fix for Pi-hole local records is the v6 API, which needs the Pi-hole admin password.
3. That password lives in Vaultwarden.

Vault needs DNS, DNS needs the vault password, and the vault password needs DNS. **Assume this deadlock will recur** and use the password-free method in section 2 to break it.

---

## 2. Password-free method to edit Pi-hole local records ✅

Use this when Vaultwarden is unreachable, or any time you want to avoid handling the admin password. Needs no Pi-hole password and applies live with **no FTL restart**.

The primary Pi-hole is **LXC 103 on pve1** (standalone Mac Mini, `root@192.168.10.193`). The `.177` address is the container, not the host.

```bash
# 1. read the current array FIRST - the write replaces it wholesale
ssh root@192.168.10.193 'pct exec 103 -- pihole-FTL --config dns.hosts'

# 2. back up before touching it
ssh root@192.168.10.193 'pct exec 103 -- cp -a /etc/pihole/pihole.toml \
    /etc/pihole/pihole.toml.bak-dnsfix-$(date +%Y%m%d)'

# 3. write the FULL array: every existing entry plus the new one.
#    Quoting through ssh + pct exec is painful, so put the write in a script,
#    `scp` it to pve1, `pct push 103` it into the container, then exec it:
#
#      new='["192.168.10.72 registry.netframe.local", ... ,"192.168.10.181 newname.kylemason.org"]'
#      pihole-FTL --config dns.hosts "$new"
#      pihole-FTL --config dns.hosts        # read back to confirm

# 4. push to the secondary immediately instead of waiting up to 15 min
ssh pve5 'pct exec 108 -- systemctl start nebula-sync.service'
```

> [!warning] It overwrites the whole array
> `pihole-FTL --config dns.hosts` is **not** an append. Omitting an existing entry deletes it. Read first, include everything, back up first. The API single-item `PUT /api/config/dns/hosts/<urlencoded "IP host">` is the non-destructive alternative but needs the admin password.

> [!info] Always edit the primary
> nebula-sync runs `FULL_SYNC=true` on CT 108 every 15 min and overwrites `.178` from `.177`. A record added only to the secondary disappears within 15 minutes.

Do not hand-edit `custom.list`; it is generated.

**Applied 2026-07-15.** Backup at `/etc/pihole/pihole.toml.bak-dnsfix-20260715` in CT 103. Added `vault`, `grafana`, `wazuh` and `console` (all `-> 192.168.10.181`), preserving the 7 existing entries. Verified all six `*.kylemason.org` names resolve on **both** `.177` and `.178` after triggering nebula-sync, and `https://vault.kylemason.org/api/config` returns 200 by name again.

**Rule going forward:** adding any new `*.kylemason.org` NPM proxy host means adding the Pi-hole local record **in the same change**. Worth periodically diffing NPM's proxy-host list against `dns.hosts`.

---

## 3. Operations Console published ✅

The NetFRAME Operations Console (`netframe-monitor` PR #30, read-only chat UI on Jarvis `:8809`) is now at **`https://console.kylemason.org`**.

**Posture: LAN/tailnet only, no WAN forward.** Same as `health.kylemason.org`. The Cloudflare A record is DNS-only (grey) and points at the private `.181`, so the name resolves everywhere but only routes from inside. No OPNsense WAN forward was added.

| Field | Value |
|---|---|
| NPM proxy host | **id 8**, `console.kylemason.org` -> `http://192.168.10.31:8809` |
| Certificate | **id 10**, Let's Encrypt via Cloudflare DNS-01, expires 2026-10-13 |
| Options | Force SSL, HTTP/2, block-exploits on; caching + websockets off |
| Access list | **id 2 "Homepage Auth"** (user `kyle`, password in Vaultwarden item `homepage`) |
| Advanced config | `proxy_read_timeout 200s; proxy_send_timeout 200s; proxy_connect_timeout 30s;` |
| Backend guard | `netframe-console-lock.service` iptables: ACCEPT `127.0.0.1` + `.181`, DROP all else |
| DNS | Cloudflare A record (pre-existing) + Pi-hole local record (added, section 2) |

**Why the timeout override**, and why this host differs from `health`: nginx defaults to `proxy_read_timeout 60s` and NPM sets no override, but the console's own `NETFRAME_CHAT_TIMEOUT` is **180s**. A `--deep` query against `qwen2.5:72b` would have died at 60s with a misleading 504. 200s is deliberately **above** the backend's 180s so the backend's own timeout fires first and returns a clean error. The console uses plain `fetch()` (no websockets, no SSE), so websocket upgrade stays off.

**Verified:** 401 with no credentials, 200 with (serves "Jarvis Operations Console"), `/api/overview` 200 in 0.09s, `/api/chat` 200 in 13s (fast mode), HTTP 301 -> HTTPS, cert CN `console.kylemason.org` issued by Let's Encrypt, direct `:8809` from the LAN still dropped.

**NPM API notes** (v2.15.1, admin `:81` firewalled to Ares `.199` per pentest F-05, so bind with `curl --interface 192.168.10.199`):
- Auth: `POST /api/tokens {identity, secret}` -> JWT.
- Cert `meta` accepts only `dns_challenge`, `dns_provider`, `dns_provider_credentials`, `propagation_seconds`, `key_type`. `letsencrypt_email` / `letsencrypt_agree` are **not** valid meta fields.
- The API **redacts** `dns_provider_credentials` on read. The Cloudflare token for an existing cert can be read from the bind mount at `/opt/nginx-proxy-manager/letsencrypt/credentials/credentials-<cert_id>` inside LXC 101 (root, `pct exec 101` from pve3).

---

## 4. Console access-list self-guard added ✅

The NPM access list on `health.kylemason.org` has silently reset to *Publicly Accessible* **twice** when the proxy host was edited and saved without re-selecting Access List + Force SSL. That is why the `page_auth` check exists.

`console.kylemason.org` is a **separate proxy host**, so its access list can detach independently, and it fronts the chat interface rather than a read-only report. Nothing was watching it.

Added a **`console_auth`** check on the synthetic `monitoring` node (`netframe-monitor` PR #31): curl the console from Jarvis with no credentials, **OK on 401** (auth enforced), **WARN on 200** (access list detached, console public). History key `monitoring.console_auth.enforced`; `page_auth`'s existing key is unchanged.

**If it ever WARNs**, fix in the NPM UI: host -> Details -> Access List = "Homepage Auth"; SSL -> Force SSL on.

> [!note] Parsing gotcha, now pinned by a test
> The classifier regexes the first `HTTP <3 digits>` out of the check output, so the echoed label must contain no 3-digit number or it is read as the status code. `test_auth_guard_labels_have_no_three_digit_number` guards both labels.

---

## 5. Verification

```
health.kylemason.org   -> 401   console.kylemason.org  -> 401     (auth enforced)
vault/grafana/wazuh/homepage/health/console  -> 192.168.10.181 on BOTH .177 and .178
console_auth  verdict=OK  http_code=401  auth_enforced=true       (live on Jarvis)
```

---

## 6. Open items

- **NPM admin password is not in Vaultwarden.** The vault holds 11 items and none is the NPM admin login (the `homepage` item is the Basic-auth credential, not the admin). There is no `INITIAL_ADMIN_PASSWORD` in `/opt/nginx-proxy-manager/docker-compose.yml`. It exists only in the owner's head, which is a real single point of failure. File it.
- **Restic passphrase filing is ambiguous.** Vaultwarden has `Ares restic backup -> Randy (repo password)`, which looks like [[Runbook/Ares-Backup-Restore]]'s repo. Whether it covers Jarvis's netframe memory-backup repo (`/root/.config/restic/netframe-pass`, from NF-AIOPS-003) is **unconfirmed**. Verify before closing that action.
- Consider an automated diff of NPM proxy hosts against Pi-hole `dns.hosts` so a missing local record is caught rather than discovered.
