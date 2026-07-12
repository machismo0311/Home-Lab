# 🌐 QuarkyLab - Off-site SSH via Cloudflare Tunnel + Access (admin)

**Tags:** #runbook #quarkylab #cloudflare #ssh #zerotrust #remote-access
**Related:** [[Runbook/QuarkyLab-Researcher-Access]] · [[Runbook/QuarkyLab-Account-Onboarding]] · [[Runbook/QuarkyLab-Student-Quickstart]]

> **STATUS (2026-07-06): tunnel LIVE, Access DEFERRED.** The Cloudflare Tunnel was created via the **API** (not the dashboard wizard below) and verified end-to-end - SSH through `quarkylab.kylemason.org` works. **Cloudflare Access is NOT yet enabled**: it needs the Zero-Trust signup (team name + payment method), a manual dashboard/card step. Until then the SSH endpoint is reachable through the tunnel and **gated by SSH keys only**. Deployed:
> - Tunnel `quarkylab` = `4c0c0c4a-8057-46f5-8e48-41493c973bd7` (remotely-managed, `config_src: cloudflare`); account `d0c8b3040ccfe3c7ddfb481e5f3baa9c`; zone `33fa4b4b8f7829f58de2f6e303073538`.
> - Ingress `quarkylab.kylemason.org` → `ssh://localhost:22`; proxied DNS CNAME → `<tid>.cfargotunnel.com`.
> - QuarkyLab: `cloudflared` 2026.6.1, systemd `cloudflared` enabled+active (connector token lives in the service config).
> - **To add Access later:** finish Zero-Trust signup, then create the self-hosted Access app for `quarkylab.kylemason.org` (§3) + email policy - scriptable via API. §1–2 below are the original dashboard walkthrough, superseded by the API method actually used.

Gives **remote students and researchers** (all off-site, nationwide) SSH into QuarkyLab with **nothing of ours exposed** - `cloudflared` on QuarkyLab dials *outward* to Cloudflare; no inbound ports, no OPNsense forward, no listening server on our public IP. Access is gated by **Cloudflare Access** (Zero Trust free tier = **50 users**, no per-seat billing) and then by each account's **SSH key** on QuarkyLab. This replaces the Headscale VPN-join path for external users (Headscale stays our *internal* admin mesh only).

**Why not Headscale/Tailscale here:** self-hosted Headscale can't be reached off-LAN without exposing it (vetoed); Tailscale's free tier caps at 6 users (the reason we left it). Cloudflare Access covers 50 users free and exposes nothing of ours.

**What *is* public:** one hostname (`quarkylab.kylemason.org`) resolves to Cloudflare's edge. There is **no origin server behind it on the internet** - every request is challenged by Access at Cloudflare's edge and only reaches QuarkyLab through the authenticated outbound tunnel. SSH stays end-to-end encrypted (SSH's own crypto) inside the tunnel.

---

## Prereqs
- `kylemason.org` already on Cloudflare (it is).
- Enable **Cloudflare Zero Trust** on the account: dash.cloudflare.com → **Zero Trust** → pick a team name → **Free** plan.
- QuarkyLab reachable for admin (LAN `192.168.10.179` / Headscale `100.64.0.7`).

## 1. Create the tunnel (dashboard/token method - best for headless QuarkyLab)
Zero Trust → **Networks → Tunnels → Create a tunnel** → *Cloudflared* → name `quarkylab`. Copy the install token it shows, then on QuarkyLab:
```bash
# install cloudflared (Debian pkg)
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bookworm main" \
  > /etc/apt/sources.list.d/cloudflared.list
apt update && apt install -y cloudflared

# run as a service with the token from the dashboard
cloudflared service install <TOKEN>
systemctl status cloudflared        # should be active; tunnel shows "HEALTHY" in the dash
```
Outbound only: cloudflared connects to Cloudflare on 443/7844. No inbound rules needed.

## 2. Publish SSH through the tunnel
In the tunnel's **Public Hostname** tab → Add a public hostname:
- **Subdomain:** `quarkylab`  **Domain:** `kylemason.org`
- **Service:** `SSH` → `localhost:22`

Cloudflare auto-creates the `quarkylab.kylemason.org` CNAME → `<tunnel-uuid>.cfargotunnel.com`.

## 3. Gate it with an Access application
Zero Trust → **Access → Applications → Add an application → Self-hosted**:
- **Application domain:** `quarkylab.kylemason.org`
- **Session duration:** e.g. 24h.
- **Policy:** *Allow* - include the users. Options (pick one, easiest first):
  - **Emails** - list each student/researcher email, **or**
  - **Emails ending in** a domain (if they share one, e.g. the university), **or**
  - an **Access Group** (`quarkylab-users`) you manage once and reference here.
- Identity: the built-in **One-time PIN** (email OTP) needs no IdP setup - fine to start. Add Google/GitHub/SSO later if wanted.

Add/remove people = edit this policy. This is the 50-user pool; it does **not** touch Headscale or consume Tailscale seats.

## 4. (Keep) per-account SSH keys on QuarkyLab
Access controls *who can reach port 22*; the SSH **key** still controls *who logs in as which account*. Unchanged workflow:
```bash
add-cluster-key.sh researcherNN "ssh-ed25519 AAAA... them@laptop"   # or studentNN
```
So a user must pass **both** Access (their email) **and** SSH key auth. Two independent gates.

> Optional hardening (later): Cloudflare **short-lived SSH certificates** - QuarkyLab's sshd trusts Cloudflare's CA and Access issues per-session certs, removing static `authorized_keys`. More setup; skip for v1, keep the existing key workflow.

## 5. Verify
- Dashboard: tunnel **HEALTHY**, Access app listed.
- From an off-site machine set up per [[Runbook/QuarkyLab-Researcher-Access]] → it should hit the Access login, then land on QuarkyLab.
- `systemctl status cloudflared` on QuarkyLab stays active across reboot (`systemctl is-enabled cloudflared`).

## Rollback / teardown
- Remove the Access application + the Public Hostname, delete the tunnel in the dashboard.
- QuarkyLab: `systemctl disable --now cloudflared` (+ `apt purge cloudflared`).
- Delete the `quarkylab` DNS record. No firewall/NAT was ever changed, nothing to undo there.

## Notes
- Headscale is untouched - still our internal admin mesh (QuarkyLab stays `100.64.0.7`). We admin QuarkyLab over Headscale/LAN; external users never touch it.
- Students still land in the SLURM/container sandbox (batch-only) and researchers get an interactive shell - that's all server-side (`sshd` Match groups + `job_submit.lua`), independent of this ingress.
- Free-tier caveats: 24h Access log retention, community support, 3-location cap - all fine here.
