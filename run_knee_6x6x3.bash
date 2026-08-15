#!/usr/bin/env bash
# 6x6x3 knee finder -- current placement, n=1, both policies.
#
# WHY.  The existing 6x6x3 sweep (results_dnn_scale_sweep) is mis-centred: delay
# is already ~30x unloaded at ls=0.02, so its knee sits BELOW the swept grid and
# was never located.  A placement comparison has to run at the knee, so find it
# first.  n=1 is deliberate -- locating a knee needs load points, not seeds.
#
# CYCLES_PER_MAC is pinned to 1.3e-4, the converter default AND the value the
# existing traffics_dnn/resnet50_bottleneck3_xb128_6x6x3.txt used.  It differs
# from 7x7x3's 2e-4, so load scales are NOT comparable across the two meshes --
# that is fine here, the placement comparison is within-mesh.
#
# Timing, 6x6x3: nodes 108, diameter 12, dwell 15 -> DP_CYCLE 3240.
#   WARMUP = 3*DP_CYCLE                      = 9720
#   SIM    = 5*t_period + WARMUP - 1000      = 5*25047 + 9720 - 1000 = 133955
# The -1000 is the reset sc_start before the measured window; without it the
# measured span is not a whole number of block passes.
set -euo pipefail
cd "$(dirname "$0")"

export DIMX=6 DIMY=6 DIMZ=3
export CONVERTER=stage2_dnn_traffic.py
export DNN_MESH=6x6x3
export DNN_CYCLES_PER_MAC=1.3e-4
export SCALE_LIST="0.008 0.010 0.012 0.014 0.016 0.018 0.020"
export SEEDS="2"
export SEL_LIST="dp bufferlevel"
export BUFFER_LIST=16
export CINTERVAL=3240
export WARMUP=9720
export SIM=133955
export JOBS=8
export OUTDIR=results_knee_6x6x3

exec ./noximrun_dnn_traffic.bash
