#!/usr/bin/env bash
# breakglass-read.sh - decrypt the break-glass credential snapshot to stdout.
# Depends ONLY on age + the local DR key: works with Vaultwarden, NPM,
# Pi-hole, and pve3 all down. Pipe to less; never redirect to a file.
#
#   ./breakglass-read.sh | less
#
# Copies: Ares ~/.config/breakglass/breakglass.age, Randy /root/breakglass.age
# (fetch with: scp root@192.168.10.187:/root/breakglass.age /tmp/ - or from
# 192.168.30.187 if VLAN 1 is impaired).
set -u
key_file="${HOME}/.config/opnsense-backup/age-key.txt"
in_file="${1:-${HOME}/.config/breakglass/breakglass.age}"
exec age -d -i "${key_file}" "${in_file}"
