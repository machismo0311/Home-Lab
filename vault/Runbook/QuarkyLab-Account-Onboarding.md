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

## Per-user exemptions
Named-account exceptions to the group lockdown above. Each is deliberately minimal — a single-user override, **not** a loosening of the group policy — and layered so the group defaults still apply to everyone else. Keep the *why* + date when adding one.

### kieron (researcher) — 2026-07-09
Building **ARID**, a RAG pipeline over the DUNE `dunereco` codebase; needs VS Code Remote-SSH plus a local Qdrant + Ollama stack.

- **SSH port-forwarding** — VS Code Remote-SSH tunnels to the server it launches, which the group's `AllowTcpForwarding no` blocks (fails at *administratively prohibited*; the Unix-socket fallback is blocked too, since `AllowTcpForwarding no` also revokes the stream-local permission flag). A named override is placed in a **lower-numbered** include file so it wins: OpenSSH applies the **first** matching `Match` block per keyword, and `Include .d/*.conf` loads in lexical order, so `40-` beats `50-`:
  ```
  # /etc/ssh/sshd_config.d/40-kieron-vscode.conf
  Match User kieron
      AllowTcpForwarding local
  ```
  Scoped to `local` forwarding only (all Remote-SSH needs); agent/X11/tunnel stay off. Apply + verify:
  ```bash
  sshd -t && systemctl reload ssh   # reload, not restart — no sessions drop
  sshd -T -C user=kieron,host=localhost,addr=127.0.0.1 | grep -i allowtcpforwarding   # -> local
  ```

- **Docker** — set up as **rootless Docker**, deliberately *not* `usermod -aG docker` (docker-group membership = host-root on a shared box, which would void the entire researcher lockdown). His compose needs no GPU and binds only unprivileged ports (Qdrant 6333 / Ollama 11434), so rootless is a clean fit. His daemon runs at `/run/user/1030/docker.sock`:
  ```bash
  apt-get install -y slirp4netns          # only missing prereq (uidmap/subuid/subgid/rootless-extras already present)
  loginctl enable-linger kieron           # user daemon runs without a login + survives reboot
  sudo -u kieron env XDG_RUNTIME_DIR=/run/user/1030 \
    DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1030/bus PATH=/usr/bin:/bin \
    dockerd-rootless-setuptool.sh install
  # PATH + DOCKER_HOST=unix:///run/user/1030/docker.sock appended to his ~/.bashrc
  ```
  `docker` / `docker compose` work as him; `docker run hello-world` verified in rootless mode.

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
