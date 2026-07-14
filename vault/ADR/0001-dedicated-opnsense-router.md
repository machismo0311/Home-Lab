# ADR-0001: Dedicated OPNsense router on Proxmox, roadmap to CARP pair

**Status:** Accepted · **Date:** 2026-07-12
**Tags:** #adr #decision #networking #ha

## Context
The lab needs a capable router, firewall, and DHCP server for a segmented multi-VLAN network (management, OOB, servers, IoT, VoIP, guest, lab). A consumer router cannot express per-VLAN firewall policy, gateway groups, or an automation API. The options were a consumer or prosumer router, a bare-metal firewall appliance, or a virtualized firewall on the existing Proxmox cluster.

## Decision
Run OPNsense as a virtual machine (VM 100) on a Proxmox node (pve2) that is dedicated to it and runs no other guests. Physical NICs are bridged into the VM for WAN and the VLAN trunk. The roadmap is to move to an OPNsense CARP high-availability pair on dedicated small-form-factor hardware, so the router is no longer a single VM on a single node. See [[High Availability/High Availability MOC]].

## Consequences
- Full firewall feature set: per-VLAN rules, multi-WAN gateway groups, and a read-only and read-write API used for backups and verification.
- Dedicating pve2 to OPNsense removes resource contention with other workloads.
- Until the CARP pair exists, the router is a single point of failure. This is mitigated today by a verified serial console and a DR-tested encrypted config backup.

## Alternatives considered
- **Consumer or prosumer router:** rejected. Insufficient VLAN and policy control, no API.
- **Bare-metal OPNsense now:** deferred, not rejected. It is the chosen HA roadmap, but virtualizing first reused existing cluster hardware and simplified snapshots and backups.
- **pfSense:** equivalent capability. OPNsense chosen for its API, plugin model, and update cadence.
