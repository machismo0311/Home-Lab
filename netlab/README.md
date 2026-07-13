# netlab — the network, as testable code

[![netlab (virtual network)](https://github.com/machismo0311/Home-Lab/actions/workflows/netlab.yml/badge.svg)](https://github.com/machismo0311/Home-Lab/actions/workflows/netlab.yml)

A [containerlab](https://containerlab.dev) topology that boots **real routers**, applies
IOS-style routing config, and is validated **end-to-end in CI**  every push spins the
network up, checks it, and tears it down. The green badge above means the routing
actually works, not just that a YAML file parses.

```
   h1 ───── r1 ═════════ r2 ───── h2
 10.10.1.10   10.0.0.0/30   10.10.2.10
   \_10.10.1.0/24        10.10.2.0/24_/
        (OSPF area 0 between r1 and r2)
```

## What it demonstrates

- **FRRouting** routers (`r1`, `r2`) configured in Cisco-IOS-style syntax — see
  [`configs/r1/frr.conf`](configs/r1/frr.conf): interface addressing, OSPF area 0,
  router-ids.
- **Dynamic routing:** the two host subnets are only reachable because OSPF forms an
  adjacency across the `r1↔r2` transit link and exchanges routes.
- **Automated verification** ([`tests/test_reachability.sh`](tests/test_reachability.sh))
  that asserts both planes:
  - *data plane* — `h1` can ping `h2` across both routers (and back),
  - *control plane* — `r1`'s OSPF neighbor is `Full` and it has learned `10.10.2.0/24`
    via OSPF (not a static/connected route).

This is the same discipline the physical NETFRAME lab is built on  VLAN/subnet design,
routing, and change validation — reduced to something a reviewer can run in 60 seconds.

## Run it locally

Requires Docker + [containerlab](https://containerlab.dev/install/).

```bash
cd netlab
sudo containerlab deploy -t netframe-lab.clab.yml
sudo bash tests/test_reachability.sh
sudo containerlab destroy -t netframe-lab.clab.yml --cleanup
```

Poke around while it's up:

```bash
sudo docker exec -it clab-netframe-r1 vtysh   # then: show ip ospf neighbor / show ip route
```

## Extend it (good CCNA practice)

- Add a third router and a second area to practice OSPF multi-area / ABR behaviour.
- Swap OSPF for static routes, then for eBGP, and watch the tests still pass (or break).
- Add an ACL on `r1` and a test that asserts a specific flow is *blocked*.
