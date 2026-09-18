# Paper 2 — RL controller over the DP substrate (re-planned 2026-09-19)

Supersedes `PAPER2-OPENING-BRIEF.md`, `RL-RESEARCH.md`, `TOPN-RL-DESIGN.md`. Read
`ROADMAP.md` "where we are" first — the facts there are binding.

## 1. Claim

A distributed RL controller sets a cost-to-go router's **budget and duty**, never its
routes. DP relaxes cost-to-go and selects ports exactly as today, for N hot sinks instead
of all destinations; other destinations use a fallback. The controller chooses set
membership, the budget N, and when the field refreshes. Learning cannot corrupt routing:
a bad policy yields a poorly chosen set; DP still routes correctly within it. Against
CURE / DeepNR / RLARA / DRLAR / LCPT-AE (all next-hop learners), the object learned is
different.

## 2. What the substrate already gives (do not re-derive, do not claim)

Design-time top-N is **measured and belongs to the Paper 1 extension**: DP/DPN = 0.998,
N@90 = 23/25/25 of 108, rotation 138–150 vs 648, N@95 = 27/38/45 for deep above-floor
cells. Stage 1's bar is therefore concrete: *match DPN at its own N*, not "retain full-DP
gain" in the abstract.

Also settled: refresh does not help (no anticipation axis, no phase-indexed comparator);
hop term cancels under minimal routing, so α and w_h are inert and no new cost term
survives; no offline quantity predicts runtime DP gain; 80–90% of bytes converge on 13–25
sinks; no torn-read hazard (`TRouter.cpp:361–385`), DP cycle = 6 × destinations.

## 3. The prize, re-estimated — the paper's central risk

Three facts shrink the target that the earlier plan assumed:

1. On the flow's own packings, **below the floor DP ≈ BL** — there is no gain there to
   protect or beat.
2. **Below-floor per-cell gain has split-half reliability r = 0.06**, so a per-cell
   switching oracle partly selects noise; the "22–29% below-floor gap" is inflated and
   must be re-estimated split-half (choose on seeds 1–4, score on 5–8) before it is cited.
3. Above the floor **DPN already equals DP** at 22% activity, flat in ci and flat in N
   around N@90.

Consequence: on stationary traffic RL has **no delay margin to win**. Its measurable
margins are:

- **N at constant gain** (stage 2). Real job: the N@90 → N@95 escalation that deep
  above-floor cells need is exactly what an adaptive-N controller should discover without
  being told the regime.
- **Duty** (stage 3). Needs the upward rotation/ci ladder (ROADMAP 0.7, ~100 runs) to size.
- **Membership under sink-set change** — the only place membership control can move delay.
  **No scenario for this exists yet.** Candidates: workload switch mid-run, dynamic
  batching, early-exit, multi-tenant co-residency, layer-group migration. Defining one
  (traffic tables with a set change at a known cycle, plus the oracle that switches with it)
  is the prerequisite for stage 1. Without it the paper is "DPN + hysteresis" — publishable
  given the literature, but not an RL paper.

## 4. Stages — one action added per stage, baselines inside the paper

**Stage 1 — membership.** Agent bids 0–3 per DP cycle; N fixed; refresh periodic.
State: own ejection-blocking bucket, in-set flag, trend. Reward: blocking reduction at own
port next cycle, oracle-normalised. Penalties: churn (flip either direction), dishonest
(bid ≥ 2, port low-blocked), missed (bid 0, port high-blocked). The budget is structural,
not a penalty. Baselines: design-time top-N (= DPN), hysteresis threshold θ_on/θ_off,
static N@95, per-regime N. **Done when:** matches DPN on all three workloads at equal N with
churn ≤ hysteresis, *and* beats both baselines on the non-stationary scenario.

**Stage 2 — budget N.** Global grow/shrink action; state adds current N; reward adds slot
cost. Baseline: grow when an outside sink exceeds the hot threshold, shrink when the
weakest member falls below. Metric: minimum N at constant gain; must rediscover N@95 where
coverage starves.

**Stage 3 — refresh.** Refresh vote replaces the periodic cycle; state adds duty; reward
adds refresh cost. Baseline: trend-triggered refresh. Metric: duty at constant gain. The
joint-control claim lives here and only if stages 1–2 hold.

Shared policy across sinks (CTDE); every agent decides locally; the only global operation
is counting to N, which rides on the DP exchange. Start as a contextual bandit to validate
the reward, then SARSA.

## 5. Protocol (essentials; full derivation in git history of TOPN-RL-DESIGN.md)

Each router holds ≤ N entries (sink id, bid, load, cycle tag); every round it unions its
list with neighbours', ranks by (bid, load, id), keeps top N, sends. Top-N under a total
order is a semilattice merge like DP's min: order-insensitive, duplicate-safe, converges
within diameter rounds — requires cycle ≥ diameter × exchange period (12 hops at 6×6×3;
fits at 162). A sink injects once at the cycle boundary; the entry is immutable. Shadow
list starts empty each cycle (no incumbents); withdrawal is absence; a bid displaced at its
own router loses everywhere. Relaxation overlaps bidding — costs depend on the list, the
list never on costs. Two tables per router: active (frozen, read by selection) and shadow
(relaxing); flip atomically. Message: tag + N entries (~17 bits) + N shadow costs — smaller
than today's all-destination vector. Correctness never depends on list agreement: mixed
DP/fallback per hop stays inside the turn model, minimal routing prevents livelock.

## 6. Scope and deferred

Scope by binding term: the claims apply to **ejection-bound** packings, where the funnel
creates link congestion DP can act on (PIL/PEL classification, ROADMAP fact 6/10).
Deferred until stage 1 holds: proxy fallback for out-of-set destinations; fallback sweep
BL / random / no-cost DP (random floor unmeasured — ROADMAP 0.4); phase feature; incumbent
bonus; variable N; lease length. Rejected: learned local cost (no downstream term);
per-sink cost weights (inert); non-sink routers as agents.

## 7. Kills

- Agent cannot match DPN at equal N → stages 2–3 do not open.
- No non-stationary scenario shows a membership-driven delay difference → paper collapses
  to DPN + hysteresis.
- Upward ladder: gain falls immediately above rotation 648 → duty axis flat.
- Re-estimated below-floor prize ≈ 0 after noise correction → drop below-floor framing
  entirely; the paper is an above-floor cost/duty result.

## 8. Reviewer attacks

"Just hotspot-aware routing" → what is learned is budget and duty, not routes; show message
and table size vs node count. "RL adds nothing over a threshold" → the baseline table; this
is now the central risk (§3). "Why not refresh faster?" → the ci/rotation results. "Random
traffic would show the same" → DNN funnel traffic throughout; random-selection floor
measured. "Does it hold beyond 6×6×3?" → second mesh as the scaling axis.
