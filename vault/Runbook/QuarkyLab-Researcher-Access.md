# 🔬 QuarkyLab - Researcher Remote Access (Cloudflare Tunnel + SSH key)

**Tags:** #runbook #quarkylab #ssh #cloudflare #onboarding #researchers
**Related:** [[Runbook/QuarkyLab-Cloudflare-Access]] · [[Runbook/QuarkyLab-Account-Onboarding]] · [[Runbook/QuarkyLab-Student-Quickstart]]

For remote researchers (off-site, nationwide) connecting to QuarkyLab. You reach it through a **Cloudflare Tunnel** - no VPN, no inbound ports on the lab side, the server's IP stays hidden. The same connection method applies to students (they just land in the SLURM sandbox - see the Student Quickstart). Researchers get a normal interactive shell; **no SLURM**.

**Current gate: your SSH key** on the `researcherNN` account. (An email-based **Cloudflare Access** gate may be layered on later; if/when it is, your first connection will also pop a one-time browser sign-in - see [[Runbook/QuarkyLab-Cloudflare-Access]]. Nothing you set up below changes when that happens.)

---

## ⚠️ Kyle-side (once per person)
> Tunnel is already stood up (see [[Runbook/QuarkyLab-Cloudflare-Access]]). Per researcher:
- Add their pubkey: `add-cluster-key.sh researcherNN "ssh-ed25519 AAAA... them@laptop"`
- Tell them their **username** (`researcherNN`).
- *(Later, if Access is enabled:)* add their email to the Access policy.

---

## Researcher steps

### 1. Create an SSH key, send the public half
```bash
ssh-keygen -t ed25519 -C "yourname@lab"        # accept default path, set a passphrase
cat ~/.ssh/id_ed25519.pub                       # send THIS line to Kyle on Discord
```
Never send the private key (`id_ed25519`, the one **without** `.pub`). You'll get back your **username** (`researcherNN`).

### 2. Install `cloudflared`
| OS | Install |
|---|---|
| macOS | `brew install cloudflared` |
| Linux (Debian/Ubuntu) | Cloudflare apt repo, or grab the binary: `https://github.com/cloudflare/cloudflared/releases/latest` |
| Windows | `winget install --id Cloudflare.cloudflared` |

### 3. Configure SSH to go through the tunnel
Add to `~/.ssh/config`:
```
Host quarkylab
    HostName quarkylab.kylemason.org
    User researcherNN
    ProxyCommand cloudflared access ssh --hostname %h
    IdentityFile ~/.ssh/id_ed25519
```

### 4. Log in
```bash
ssh quarkylab
```
`cloudflared` routes you through the tunnel and SSH authenticates with your key - you're in. (First time, accept the host-key prompt with `yes`.)

You land in a normal shell on your home (`/workspace/researchers/researcherNN`). The GPU (RTX 8000, 48 GB), CUDA, and ML toolchain are available directly - run your jobs as on any Linux box. See the Researcher Guide for the actual working commands.

---

## Troubleshooting
| Symptom | Fix |
|---|---|
| `cloudflared: command not found` | Install it (step 2) and ensure it's on `$PATH`. |
| Connection hangs / won't start | Confirm the `~/.ssh/config` block from step 3 is present; retry. Check `quarkylab.kylemason.org` resolves. |
| `Permission denied (publickey)` | Wrong username, or your pubkey isn't on the account yet - confirm `researcherNN` and that Kyle ran `add-cluster-key.sh`. Passwords are disabled; key-only. |
| *(If Access is later enabled)* browser sign-in denied | Your email isn't in the Access policy - ask Kyle to add it. |

## Access model (FYI)
Researcher accounts (`researcher01`–`06`) are **key-only** - no password/keyboard-interactive login, no port/X11/agent forwarding (`/etc/ssh/sshd_config.d/50-cluster-access.conf`, scoped to the `researchers` group). No sudo. Homes on the `workspace` ZFS pool. Unlike students, researchers are **not** confined to the SLURM/container sandbox. The tunnel exposes **only** QuarkyLab's SSH - no other lab host is reachable. Until the optional Access layer is added, that SSH endpoint is reachable through Cloudflare and gated by SSH keys alone.
