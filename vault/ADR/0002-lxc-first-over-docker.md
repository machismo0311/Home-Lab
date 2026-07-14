# ADR-0002: LXC-first over Docker for services

**Status:** Accepted · **Date:** 2026-07-12
**Tags:** #adr #decision #compute

## Context
The cluster runs many self-hosted services (reverse proxy, secrets, monitoring, DNS, media, chat UI, and more). Proxmox supports both full VMs and system containers (LXC), and Docker can run inside either. A default packaging model was needed so services are consistent to deploy, back up, and reason about.

## Decision
Prefer Proxmox LXC system containers for services. Use Docker only when a service ships primarily as a container image or a compose stack that is impractical to run natively. Persistent services get a systemd unit, and secrets live in Vaultwarden rather than in image layers or compose files.

## Consequences
- LXCs are lightweight, start fast, and integrate directly with Proxmox Backup Server, so each service is captured in the nightly PBS job at the container level.
- Resource use and host visibility are better than nested Docker on a VM.
- The trade-off is less portability than a Docker image and no compose ecosystem by default. A few services that are Docker-native (for example Vaultwarden) still run Docker Compose inside an LXC, which is accepted.

## Alternatives considered
- **Docker everywhere:** rejected as the default. It adds a nesting layer on Proxmox and duplicates what LXC already provides, though it is kept for genuinely container-native services.
- **Full VMs per service:** rejected as the default. Heavier on RAM and disk for services that do not need kernel isolation.
