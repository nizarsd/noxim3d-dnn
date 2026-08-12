# Noxim3D-DNN

DNN-aware adaptive routing research on a 3D Network-on-Chip. This repository is the
**Stage 2+ working line** of the "NoC for AI" project, extending the validated
[noxim3d](https://github.com/nizarsd/noxim3d) simulator (itself forked from
[Noxim](https://github.com/davidepatti/noxim)) with DNN inference traffic generation
and, in later stages, reinforcement-learning selection policies.

**Base simulator (frozen):** `nizarsd/noxim3d` holds the Stage 1 validated state — 3D
deadlock-free odd–even routing and the DP congestion-aware selection policy, with the
DP-vs-bufferlevel study complete. That repository is not modified further; all DNN-line
work happens here.

## Project stages

1. Validate 3D Noxim + odd–even routing — **complete** (inherited from base repo).
2. Generate DNN traffic traces (ResNet-50, VGG-16) — **in progress**.
3. Baseline characterisation: DNN vs synthetic traffic.
4. Minimal RL selection agent, generic congestion objective.
5. Run generic RL agent on DNN traffic, unmodified.
6. Analyse distinguishing features of DNN traffic (evidence-driven).
7. DNN-aware RL router — the novel contribution.

See `CLAUDE.md` for detailed design notes and open decisions.

## Highlights

- **Novel 3D deadlock-free adaptive routing** implementing the odd–even turn model in
  three dimensions, as introduced in the IET paper (see [Citation](#citation)):
  - **3D Odd–Even (OE)** — dimension-wise odd–even turn restrictions extended to the
    vertical dimension (`-routing dwoddeven`).
  - **3D Odd–Even Balanced (OEB)** — a balanced variant that spreads turns more evenly
    across the mesh for better path diversity (`-routing oddevenbalanced`).
  Both preserve deadlock freedom by construction and fall back to the 2D odd–even turn
  model when `Z == 1`.
- **DP selection policy** — a distributed selection unit that builds a multi-hop
  congestion *cost-to-go* field (`-sel dp`), compared against the classic local
  **buffer-level** heuristic (`-sel bufferlevel`). DP's turn legality mirrors the router
  but is source-independent.
- Inherits Noxim's flit-level modeling: wormhole switching, per-router buffers,
  configurable traffic patterns, and delay/throughput/energy statistics.

## Build

Requires **SystemC 2.3.3**.

1. Edit `Makefile.defs` and set `SYSTEMC` to your SystemC install path.
2. Build:

```bash
make
```

This produces the `noxim` binary. Object files and the binary are gitignored — rebuild
locally.

## Quick start

Run a 5×5×3 mesh with 3D odd–even-balanced routing and the DP selection policy:

```bash
./noxim \
  -dimx 5 -dimy 5 -dimz 3 \
  -buffer 16 \
  -routing oddevenbalanced \
  -sel dp \
  -pir 0.02 poisson \
  -traffic transpose1 \
  -warmup 3000 -sim 20000 -seed 2
```

### Selected options

| Flag | Values | Meaning |
|------|--------|---------|
| `-dimx / -dimy / -dimz` | ints | Mesh dimensions (X × Y × Z). |
| `-routing` | `dwoddeven`, `oddevenbalanced`, `xy`, `westfirst`, `northlast`, `negativefirst`, `oddeven`, `dyad <t>`, `fullyadaptive`, `table <f>`, … | Routing algorithm. `dwoddeven` = 3D OE, `oddevenbalanced` = 3D OEB. |
| `-sel` | `dp`, `bufferlevel`, `nop`, `random` | Selection strategy. |
| `-buffer` | int | Per-input-channel buffer depth (flits). |
| `-pir` | float + `poisson`/`burst`/… | Packet injection rate and process. |
| `-traffic` | `random`, `transpose1`, `table <f>`, … | Traffic pattern. |
| `-cinterval` | int | Congestion-sampling interval used by DP. |
| `-warmup / -sim` | ints | Warm-up and measured simulation windows (cycles). |
| `-dpsettle` | int (default 0) | DP settle = N · dp_pass cycles before applying a new config. `0` = continuous reconvergence (best-or-tied). |
| `-seed` | int | RNG seed. |

## Running sweeps

Helper scripts drive PIR and buffer-size sweeps with DP-aware timing auto-derived from
the mesh (`DP_CYCLE = 2·nodes·(diameter+3)`):

- `noximrun.bash` — single run.
- `noximrun_buffer_sweep.bash` — buffer-size sweep.
- `noximrun_buffer_sweep_parallel.bash` — parallel sweep (`JOBS` knob; deterministic,
  bit-identical to the sequential version).

Results land in `results_*/` directories (gitignored — regenerate rather than commit).

## Key source files

- `TRouter.cpp` / `TRouter.h` — router, routing algorithms, selection policies.
- `DPNode.cpp` / `DPNode.h` — DP cost-to-go computation unit.
- `TNoC.cpp` / `TNoC.h` — top-level NoC topology and wiring.
- `TProcessingElement.cpp` — per-node traffic generation/injection.
- `TGlobalStats.cpp` / `TPower.cpp` — statistics and power modeling.

## History

Noxim3D builds on a lineage of NoC simulation work:

- **Original Noxim** was created at the **University of Catania** (Italy) by Maurizio
  Palesi and colleagues, as an open-source, SystemC-based, cycle-accurate simulator for 2D NoCs.
- The **3D NoC extension and the 3D deadlock-free adaptive routing** (3D odd–even and odd–even-balanced turn
  models) and the congestion-aware routing/selection work — including the DP distributed
  cost-to-go selection policy — were developed at the **University of Newcastle upon
  Tyne** (UK); see the IET paper in [Citation](#citation).
- **The NoC-for-DNN line of work** — DNN-style traffic modeling and the
  reinforcement-learning routing research documented here — is being carried out at the
  **University of Baghdad** (Iraq), building on the frozen `nizarsd/noxim3d` base.

## Citation

The 3D odd–even (OE) and odd–even-balanced (OEB) deadlock-free routing algorithms
implemented here are from:

> N. Dahir, T. Mak, R. Al-Dujaily, and A. Yakovlev, "Highly adaptive and
> deadlock-free routing for three-dimensional networks-on-chip," _IET Computers &
> Digital Techniques_, vol. 7, no. 6, pp. 255–263, 2013.
> doi: [10.1049/iet-cdt.2013.0029](https://doi.org/10.1049/iet-cdt.2013.0029)

If you use Noxim3D in academic work, please cite the paper above and the original
[Noxim](https://github.com/davidepatti/noxim) simulator.

## License

Noxim3D inherits the license of the upstream Noxim project (Licensed under the GNU GPL-2.0). See the original
Noxim repository for details.
