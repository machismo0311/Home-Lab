# ============================================================================
# NetFRAME Homelab — Bash Aliases
# Ares admin workstation (machismo@Ares)
# ============================================================================

# ── Cluster SSH shortcuts ────────────────────────────────────────────────────
alias pve2='ssh root@192.168.10.204'
alias pve3='ssh root@192.168.10.201'
alias pve4='ssh root@192.168.10.202'
alias pve5='ssh root@192.168.10.203'
alias randy='ssh root@192.168.10.187'
alias quarkylab='ssh root@quarkylab.netframe.local'
alias jarvis='ssh root@192.168.10.31'

# ── iDRAC / IPMI shortcuts ───────────────────────────────────────────────────
alias idrac-quarky='ssh root@192.168.10.20'
alias idrac-jarvis='ssh root@192.168.10.21'
alias ipmi-randy='ssh root@192.168.10.22'

# ── Switch ───────────────────────────────────────────────────────────────────
alias switch='ssh mason@192.168.10.50'
alias ex3400='ssh mason@192.168.10.50'

# ── PBS ──────────────────────────────────────────────────────────────────────
alias pbs='ssh root@192.168.10.187'
alias pbs-ui='xdg-open https://192.168.10.187:8007'

# ── Proxmox UIs ──────────────────────────────────────────────────────────────
alias pve-ui='xdg-open https://192.168.10.204:8006'
alias randy-ui='xdg-open https://192.168.10.187:8006'

# ── Cluster health ───────────────────────────────────────────────────────────
alias cluster-status='ssh root@192.168.10.204 "pvecm status && pvecm nodes"'
alias cluster-nodes='ssh root@192.168.10.204 "pvecm nodes"'

# ── Randy storage ────────────────────────────────────────────────────────────
alias randy-pool='ssh root@192.168.10.187 "zpool status datastore && zpool list"'
alias randy-drives='ssh root@192.168.10.187 "storcli64 /c0/eall/sall show"'

# ── OPNsense ─────────────────────────────────────────────────────────────────
alias opnsense-console='ssh root@192.168.10.204 "qm terminal 100"'
alias opnsense='xdg-open https://192.168.10.1'

# ── Pi-hole ──────────────────────────────────────────────────────────────────
alias pihole='xdg-open http://192.168.10.177/admin'

# ── Git shortcuts ─────────────────────────────────────────────────────────────
alias homelab='cd ~/Home-Lab'
alias gst='git status'
alias gad='git add -A'
alias gcm='git commit -m'
alias gph='git push'
alias gpl='git pull'
alias glog='git log --oneline --graph --decorate -10'

# ── General convenience ───────────────────────────────────────────────────────
alias ll='ls -lah'
alias la='ls -A'
alias l='ls -CF'
alias grep='grep --color=auto'
alias df='df -h'
alias du='du -sh'
alias free='free -h'
alias ports='ss -tulnp'
alias myip='ip -br addr show'
alias update='sudo apt update && sudo apt dist-upgrade -y'

# ── Obsidian vault ────────────────────────────────────────────────────────────
alias vault='cd ~/Vaults/homelab-vault'

# ── History logging (forensic audit trail) ────────────────────────────────────
export HISTTIMEFORMAT="%Y-%m-%d %T "
export HISTSIZE=10000
export HISTFILESIZE=20000
export HISTCONTROL=ignoredups:erasedups
shopt -s histappend

# Write timestamped history to daily log
mkdir -p ~/.logs
PROMPT_COMMAND='echo "$(date +"%Y-%m-%d %H:%M:%S") $(pwd) $(history 1 | sed "s/^[ ]*[0-9]*[ ]*//")" >> ~/.logs/bash-history-$(date +%Y-%m-%d).log'
