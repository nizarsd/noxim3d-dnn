#!/usr/bin/env bash
# n=30 confirmation sweep at the single load point that the n=10 power analysis
# says actually converts.
#
# WHY ONLY ls=0.022.  Required seeds per arm for Welch t=2.8, estimated from the
# n=10 spreads in results_block_7x7x3:
#     ls=0.012 n=21   ls=0.016 n=29   ls=0.020 n=42
#     ls=0.022 n=28  <-- this one       ls=0.025 n=53   ls=0.028 n=104
# At n=30 only 0.022 clears, so a 3-point x 30-seed grid would have spent two
# thirds of its runs on points that still miss significance.  0.022 is cheap
# despite a large spread because the effect is large relative to it: 11.07
# cycles of separation, DP sd 6.4 vs BL sd 19.6.
#
# Timing is pinned, NOT auto-derived: SIM=206674 makes the measured window an
# exact whole number of block passes.  The sweep script's own formula
# (SIM_DP_CYCLES x DP_CYCLE = 399840) does not, because the 1000-cycle reset
# shifts the phase.  206674 = 5 x t_period (38536) + WARMUP (14994) - 1000.
#
# The seeds are 2..118 step 4, a superset pattern of the n=10 run's 2..38, but
# these results are NOT poolable with results_block_7x7x3: that sweep ran at
# simulation_time 207674, a different window.

set -euo pipefail
cd "$(dirname "$0")"

export DIMX=7 DIMY=7 DIMZ=3
export CONVERTER=stage2_dnn_traffic.py
export DNN_MESH=7x7x3

# MUST be set explicitly.  The converter's default is 1.3e-4, left over from the
# 6x6x3 tuning; every 7x7x3 table generated so far -- the n=10 sweep, the
# committed traffics_dnn/ block table -- used 2e-4.  At the default the block
# runs 1.54x faster (t_period 25047 not 38536), which moves the operating point
# and breaks the SIM alignment below.  Verified against the emitted header.
export DNN_CYCLES_PER_MAC=2e-4
export SCALE_LIST="0.022"
export SEEDS="$(seq 2 4 118 | tr '\n' ' ')"
export BUFFER_LIST=16
export SEL_LIST="dp bufferlevel"
export SIM=206674
export WARMUP=14994
export CINTERVAL=4998
export JOBS=8
export OUTDIR=results_block_ls022_n30

exec ./noximrun_dnn_traffic.bash
