# 🔑 QuarkyLab — Student/Researcher SSH Onboarding
**Tags:** #runbook #quarkylab #ssh #onboarding #students #researchers
**Related:** [[Runbook/QuarkyLab-Student-Quickstart]] · [[Runbook/QuarkyLab-Phase04-GPU-Sharing-2026-07-02]] · [[Compute/Dell R730 - ML Node]]

---

## Access model
Student (`student01`–`20`) and researcher (`researcher01`–`06`) accounts are **key-only** — passwords are locked; no password/keyboard-interactive login; no TCP/X11/agent forwarding or tunneling. Enforced by `/etc/ssh/sshd_config.d/50-cluster-access.conf`:
```
Match Group students,researchers
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    X11Forwarding no
    AllowTcpForwarding no
    AllowAgentForwarding no
    PermitTunnel no
```
This is **scoped** to those groups — root/fernanda/admin auth is unchanged.

## Onboard a person's key (as root on QuarkyLab)
Collect their **public** key (e.g. `ssh-ed25519 AAAA... alice@laptop`), then:
```bash
add-cluster-key.sh student03 "ssh-ed25519 AAAA... alice@laptop"
#   or pipe a file:
add-cluster-key.sh researcher02 < alice.pub
```
The helper (`/usr/local/sbin/add-cluster-key.sh`):
- only accepts `student##` / `researcher##` accounts (refuses root, fernanda, etc.),
- validates the key with `ssh-keygen -l`,
- creates `~/.ssh` (700) + `authorized_keys` (600) owned by the user,
- de-duplicates.

They then log in with their private key:
```bash
ssh studentNN@192.168.10.179
```

## Remove / rotate a key
```bash
# remove by comment/fingerprint match, then confirm
sed -i '/alice@laptop/d' /workspace/students/student03/.ssh/authorized_keys
```

## Notes
- Homes live on the `workspace` ZFS pool (`/workspace/students/<u>`, `/workspace/researchers/<u>`) — see [[Infrastructure/QuarkyLab Storage]].
- Students are **batch-only** by policy; `srun --pty` currently bypasses the container/VRAM cap (Phase 06 to close).
- Give students the [[Runbook/QuarkyLab-Student-Quickstart]] (also at `/data/shared/QUICKSTART.md`).
