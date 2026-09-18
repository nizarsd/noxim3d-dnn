# Claude Code prompt — below-floor loss decomposition (runtime attribution)

## Context (revised 2026-09-19 — read ROADMAP.md "where we are" first)

C8: below the port floor, DP captures 71–78% of the switching-oracle bound; the deficit is
temporal. The extension needs the mechanism behind C8: where the below-floor loss sits and
whether any routing policy could recover it. This is also **CiN's opening exhibit**: the
drain share is the term in-network reduction attacks, and with the PIL/PEL classification it
says which packings CiN can help.

Hypothesis: most of the below-floor loss is ejection drain at the hot sinks — invariant to
selection policy and to refresh rate — so the capture ceiling for any routing policy below
the floor is bounded by one minus the drain share.

Four results since this prompt was written change its execution, not its aim:

- **Refresh is settled, no new runs needed.** The ci sweep retired the 648 convention and
  DPN runs a 4.5× faster rotation (138–150) at iso-performance. Use those existing matched-seed
  runs as the refresh control wherever this prompt says "DP-162".
- **The oracle reference is noise-inflated.** Below-floor per-cell gain has split-half seed
  reliability r = 0.06, so a per-cell switching oracle partly selects noise. Compute the
  oracle split-half (choose on seeds 1–4, score on 5–8); the corrected gap is the
  decomposition's denominator.
- **Add the c16 matrix cells** (coherent: 3 workloads, one packing rule, 8 seeds, own-knee
  rungs) beside the paper's below-floor sets. Note that on c16 DP ≈ BL below the floor, so
  there the decomposition target is BL-vs-oracle, or drain as a share of total delay.
- **Instrumentation gap is narrower than assumed.** BARRIERTRACE already logs per-packet
  inject→delivery (`TStats.cpp:74`); what is missing is the arrive-at-sink-router→eject
  split, i.e. one counter behind a flag.

Two turns. Turn 1 is investigate-only. Do not run new simulations in Turn 1.

Attribution is on mean delay and blocking cycles only. p99 does not decompose across links,
sinks or phases; report it alongside as headline, never as the thing being split.

---

## Turn 1 — instrumentation audit and plan (no runs)

Produce `docs/LOSS-DECOMPOSITION-PLAN.md`. File paths and line numbers for every claim.

1. **What DPTRACE logs today.** Per-link blocking? Per-sink ejection-queue occupancy?
   Per-packet timestamps (inject, arrive-at-sink-router, eject)? Per phase window? The
   validation run used seven links — was that a ceiling or a choice? What is the overhead
   of tracing every link and every sink on 6×6×3 for a full run?
2. **What is missing.** To split delay into (a) ejection drain = cycles between arrival at
   the sink router and ejection, (b) reconvergence lag = excess blocking in a fixed window
   after each phase boundary relative to the mid-phase steady state, (c) residual link
   blocking = everything else, what must be added? Name the counters and where they hook.
3. **Phase boundaries.** How are phase windows defined from the traffic table (t_on /
   t_off / t_period per flow)? Is there an existing phase-index function (the phase-indexed
   DP spec would use it)? If not, specify one.
4. **Reference runs.** Identify the below-floor efficiency-gap runs (BL, DP, oracle) for the
   three workloads: paths, seeds, densities. The decomposition must run on the same seeds.
5. **Refresh control.** Use the existing fast-rotation runs (DPN at 138–150, ci sweep) as
   the refresh arm — confirm their seeds match the 648 references rather than rerunning.
6. **Decomposition method.** Write the exact formula: per packet, delay = inject-to-arrive
   (link + lag) + arrive-to-eject (drain). Lag is separated from link by the phase-window
   test in 2(b). Sum per sink, per phase, per workload. Define the below-floor loss as
   (DP delay − oracle delay) and express each component as a share of it.
7. **Sanity checks.** Components must sum to total delay within 1%. Drain share must be
   invariant across BL, DP and the fast-rotation arm (it is a property of the arrival rate and
   the port, not the policy); if it is not, say so — that would falsify the hypothesis.

End with READY / NEEDS INSTRUMENTATION (list) / BLOCKED (reason).

---

## Turn 2 — run and report (gated on Turn 1)

1. Add the missing counters from Turn 1 Q2 behind a flag; flag absent → bit-identical to
   HEAD on transpose1.
2. Rerun the below-floor references (BL, DP, oracle) on the three workloads plus the c16
   matrix cells, same seeds, tracing on; the fast-rotation arm comes from existing DPN/ci
   runs. 8 seeds matches the campaign standard (the split-half checks need the pairing).
3. Report per workload, per phase, per hot sink: drain, lag, link — cycles and share of
   below-floor loss. Roll up to per workload. Report the drain-share invariance check
   across the four policies.
4. Report the derived bound: capture ceiling for any routing policy = 1 − drain share,
   per workload, against the actual capture — and against the split-half-corrected gap,
   not the raw per-cell oracle.
5. One figure: stacked bar per workload of below-floor loss into drain / lag / link, with
   DP-648 and the fast-rotation arm side by side so the lag bar's response to refresh is visible. Vector
   PDF, single column, plus PNG.
6. `docs/LOSS-DECOMPOSITION-RESULTS.md`. Do not alter defaults.

## Out of scope

Any policy that would recover the loss (Paper 2). Implementing in-network reduction or
scatter (CiN) — this prompt only measures the term CiN would attack. Changes to routing,
selection, DP, or the turn model.

## What the result feeds

The extension's closing result and CiN's opening motivation: if drain dominates and is
policy-invariant, the only remaining levers are more ejection ports (accumulator tiles) or
fewer arriving packets (in-network reduction).
