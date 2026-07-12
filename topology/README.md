# topology — diagram-as-code

[![diagram-as-code](https://github.com/machismo0311/Home-Lab/actions/workflows/diagram.yml/badge.svg)](https://github.com/machismo0311/Home-Lab/actions/workflows/diagram.yml)

The network diagram is **generated from a source of truth**, not hand-drawn — so it can't
silently drift from reality.

```
inventory.yml  ──►  gen_diagram.py  ──►  topology.mmd  (Mermaid, renders on GitHub)
 (source of truth)     (generator)         (committed artifact)
```

- [`inventory.yml`](inventory.yml) — the nodes and links, in one human-editable file.
- [`gen_diagram.py`](gen_diagram.py) — renders it to Mermaid, with role-based styling.
- [`topology.mmd`](topology.mmd) — the generated diagram (committed).
- CI ([`.github/workflows/diagram.yml`](../.github/workflows/diagram.yml)) runs
  `gen_diagram.py --check` on every push and **fails the build if the committed diagram
  is stale** — edit the inventory, forget to regenerate, and the pipeline catches it.

## Usage

```bash
python3 topology/gen_diagram.py           # regenerate topology.mmd
python3 topology/gen_diagram.py --check    # CI mode: exit 1 if out of date
```

Only dependency is `pyyaml`.

## Why

A diagram that's maintained by hand is wrong the day after you draw it. Driving it from
the same inventory that (could) feed Ansible/NetBox means the picture, the docs, and the
automation all read from one source — and CI proves they agree.

See also the richer hand-authored reference in
[`NetFRAME-Network-Topology.md`](NetFRAME-Network-Topology.md).
