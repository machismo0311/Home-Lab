# netlab — the network, as testable code

[![netlab (virtual network)](https://github.com/machismo0311/Home-Lab/actions/workflows/netlab.yml/badge.svg)](https://github.com/machismo0311/Home-Lab/actions/workflows/netlab.yml)

A [containerlab](https://containerlab.dev) topology that boots **real routers**, applies
IOS-style routing config, and is validated **end-to-end in CI** — every push spins the
network up, checks it, and tears it down. The green badge above means the routing
actually works (and *survives a link failure*), not just that a YAML file parses.

```
                    primary: r1 ⇄ r2  (OSPF cost 10)
   h1 ───── r1 ═══════════════════════ r2 ───── h2
 10.10.1.10   ╲                       ╱   10.10.2.10
   10.10.1.0/24 ╲__ r3 (transit) __╱      10.10.2.0/24
                  backup: r1 ⇄ r3 ⇄ r2 (OSPF cost 20)
```

There are **two paths** between the host subnets. OSPF prefers the direct `r1↔r2`
link; when it fails, traffic reroutes through `r3` with no loss of connectivity —
and reverts when the link comes back.

## What it demonstrates

- **FRRouting** routers (`r1`, `r2`, `r3`) configured in Cisco-IOS-style syntax — see
  [`configs/r1/frr.conf`](configs/r1/frr.conf): interface addressing, OSPF area 0,
  point-to-point transit links, router-ids, and explicit `ip ospf cost` for
  deterministic path selection.
- **Dynamic routing:** the host subnets are only reachable because OSPF forms
  adjacencies across the transit links and exchanges routes.
- **Redundancy & failover:** a second path (`r1↔r3↔r2`) sits at a higher cost as a
  hot standby; OSPF reconverges onto it when the primary link drops.
- **Automated verification** of both scenarios:
  - [`tests/test_reachability.sh`](tests/test_reachability.sh) — steady state:
    *data plane* (`h1`↔`h2` ping across the routers) and *control plane* (`r1`'s
    OSPF neighbor is `Full`, `10.10.2.0/24` learned via OSPF).
  - [`tests/test_failover.sh`](tests/test_failover.sh) — resilience: assert the
    primary (direct) path is in use, **down the `r1↔r2` link**, assert OSPF
    reroutes `h1↔h2` through `r3` (next-hop flips to `10.0.1.2`) with connectivity
    intact, then **restore** the link and assert the route reverts to the direct path.

This is the same discipline the physical NETFRAME lab is built on — VLAN/subnet design,
redundant routing, and change validation — reduced to something a reviewer can run in
60 seconds.

## Addressing

| Link | Subnet | Role |
|---|---|---|
| h1 ↔ r1 | `10.10.1.0/24` | host access |
| h2 ↔ r2 | `10.10.2.0/24` | host access |
| r1 ↔ r2 | `10.0.0.0/30` | **primary** transit (cost 10) |
| r1 ↔ r3 | `10.0.1.0/30` | backup transit (cost 10) |
| r2 ↔ r3 | `10.0.2.0/30` | backup transit (cost 10) |

Router-ids: `r1 = 1.1.1.1`, `r2 = 2.2.2.2`, `r3 = 3.3.3.3`. Direct path cost `10` vs
backup path cost `20`, so the direct link always wins until it fails.

## Run it locally

Requires Docker + [containerlab](https://containerlab.dev/install/).

```bash
cd netlab
sudo containerlab deploy -t netframe-lab.clab.yml
sudo bash tests/test_reachability.sh
sudo bash tests/test_failover.sh
sudo containerlab destroy -t netframe-lab.clab.yml --cleanup
```

Watch the failover happen by hand:

```bash
sudo docker exec clab-netframe-r1 vtysh -c 'show ip route 10.10.2.0/24'  # via 10.0.0.2 (r2)
sudo docker exec clab-netframe-r1 ip link set eth2 down                  # kill primary
sudo docker exec clab-netframe-r1 vtysh -c 'show ip route 10.10.2.0/24'  # via 10.0.1.2 (r3)
```

## Extend it (good CCNA practice)

- Give `r3` a second OSPF area and make it an ABR to practice multi-area / LSA types.
- Add [BFD](https://docs.frrouting.org/en/latest/bfd.html) to the transit links and
  compare failover time against the OSPF dead-interval alone.
- Swap OSPF for static routes, then for eBGP, and watch the tests still pass (or break).
- Add an ACL on `r1` and a test that asserts a specific flow is *blocked*.
