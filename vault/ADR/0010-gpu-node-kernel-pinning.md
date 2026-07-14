# ADR-0010: Kernel pinning on GPU nodes for the NVIDIA driver stack

**Status:** Accepted · **Date:** 2026-07-12
**Tags:** #adr #decision #compute #gpu

## Context
The two Dell R730 GPU nodes (QuarkyLab with an RTX 8000, Jarvis with two RTX 6000) run the NVIDIA 550 driver, which builds against a specific kernel. Proxmox ships newer kernels on upgrade, and kernels 6.17 and later break the 550 driver, which would silently take the GPUs offline after a routine `apt` upgrade or reboot.

## Decision
Pin both GPU nodes to kernel `6.14.11-9-pve` through `GRUB_DEFAULT`, and treat kernel upgrades and GRUB default changes on these two nodes as prohibited without first revalidating the driver stack. The pin is recorded as a hard safety rule in the node CLAUDE.md.

## Consequences
- The GPU stack stays stable and verified (nvidia-smi reports full VRAM on driver 550.163.01).
- The two nodes do not receive newer-kernel security fixes and features until the driver stack is deliberately revalidated on a newer kernel.
- It requires operator discipline to avoid an accidental kernel upgrade, so the rule is documented prominently and the pin is asserted in GRUB rather than left to default behavior.

## Alternatives considered
- **Track the latest kernel with DKMS rebuilds:** rejected. Breaks on 6.17 and later, and an unattended upgrade could disable the GPUs between reboots.
- **Containerized or toolkit-managed drivers:** rejected for now. Adds a layer without solving the host-kernel-to-driver coupling for bare-metal Proxmox.
