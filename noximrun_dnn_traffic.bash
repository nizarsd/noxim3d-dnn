#!/usr/bin/env bash
set -euo pipefail

# DNN traffic-table sweep -- Stage 2.
#
# Parallel (selection x load-scale x buffer x seed) sweep under a DNN-derived
# traffic table, as the DP-vs-BL analogue of the Stage-1 PIR sweeps.
#
# TWO THINGS DIFFER FROM noximrun_buffer_sweep_parallel.bash, both forced by how
# table-based traffic actually works in the simulator:
#
#   1. `-traffic table FILE` is TWO argv words.  The Stage-1 script passes
#      `-traffic "$TRAFFIC"` quoted, which hands the parser a single word
#      "table FILE"; strcmp against "table" then fails and it silently falls
#      through to INVALID_TRAFFIC (CmdLineParser.cpp:342).  Here the flag and the
#      filename are separate arguments.
#
#   2. `-pir` DOES NOTHING in table mode, so the Stage-1 PIR sweep is a no-op.
#      TProcessingElement::canShot takes the table branch and reads its threshold
#      only from getCumulativePirPor (TProcessingElement.cpp:191);
#      TGlobalParams::packet_injection_rate is never consulted.  Every point in a
#      PIR_LIST would produce byte-identical results.
#      => The load axis is swept by REGENERATING THE TABLE at each LOAD_SCALE,
#         which rescales every row's pir.  That is what SCALE_LIST does below.
#
# Also note: the table branch skips throt_pir, so router throttling is inactive
# under table traffic -- unlike every synthetic pattern.  Keep that in mind when
# comparing these numbers against the Stage-1 baselines.
#
# Each noxim run is single-threaded, CPU-bound and deterministic (fixed -seed),
# so parallel execution gives per-run numbers identical to a sequential sweep.
# Each job writes its own row file; rows are concatenated after all jobs finish.

BIN=${BIN:-./noxim}
CONVERTER=${CONVERTER:-stage2_dnn_traffic.py}
PYTHON=${PYTHON:-python3}

# Must match the mesh the converter's placement boxes are built for; the table
# header is checked against these below rather than trusted.
DIMX=${DIMX:-6}
DIMY=${DIMY:-6}
DIMZ=${DIMZ:-3}

ROUTING=${ROUTING:-oddevenbalanced}
SEL_LIST=${SEL_LIST:-"dp bufferlevel"}

# The load axis. Each value regenerates the whole table with every pir scaled by
# it. At 1.0 the table carries the raw DNN volume, which sits far above the
# Stage-1 6x6x3 knee (PIR ~= 0.020) -- so this sweep runs well BELOW 1.
SCALE_LIST=${SCALE_LIST:-"0.01 0.02 0.03 0.05 0.08 0.12 0.20"}

SEEDS=${SEEDS:-"2 6 10"}
BUFFER_LIST=${BUFFER_LIST:-"16"}

# Fixed packet size (STAGE2.md SS9.1). `-size N N` yields an exactly fixed size
# because randInt(min,max) returns min when min==max. Per-flow volume lives in
# pir (packet COUNT), never in size, so this MUST match the converter's
# PACKET_FLITS or the emitted packet counts mean the wrong number of bytes.
PACKET_SIZE=${PACKET_SIZE:-16}

OUTDIR=${OUTDIR:-results_dnn_scale_sweep}
TABLE_DIR=${TABLE_DIR:-$OUTDIR/tables}

JOBS=${JOBS:-$(nproc)}

# ------------------------------------------------------------
# DP-aware timing (same derivation as the Stage-1 scripts)
# ------------------------------------------------------------
NUM_NODES=$((DIMX * DIMY * DIMZ))
DIAMETER=$(((DIMX - 1) + (DIMY - 1) + (DIMZ - 1)))
DP_DWELL=${DP_DWELL:-$((DIAMETER + 3))}
DP_PHASES=${DP_PHASES:-2}
DP_CYCLE=$((DP_PHASES * NUM_NODES * DP_DWELL))
WARMUP_DP_CYCLES=${WARMUP_DP_CYCLES:-3}
# 80, not the Stage-1 default of 20: the DNN table has a real period
# (t_period ~= 25k for this block) and SIM must cover enough block passes to
# average over. 80*DP_CYCLE gives ~10 passes. See the converter's timing report.
SIM_DP_CYCLES=${SIM_DP_CYCLES:-80}
MIN_WARMUP=${MIN_WARMUP:-1000}
MIN_SIM=${MIN_SIM:-5000}
AUTO_WARMUP=$((WARMUP_DP_CYCLES * DP_CYCLE))
AUTO_SIM=$((SIM_DP_CYCLES * DP_CYCLE))
(( AUTO_WARMUP < MIN_WARMUP )) && AUTO_WARMUP=$MIN_WARMUP
(( AUTO_SIM < MIN_SIM )) && AUTO_SIM=$MIN_SIM
WARMUP=${WARMUP:-$AUTO_WARMUP}
SIM=${SIM:-$AUTO_SIM}
CINTERVAL=${CINTERVAL:-$DP_CYCLE}

echo "Timing:"
echo "  NUM_NODES=$NUM_NODES  DIAMETER=$DIAMETER  DP_DWELL=$DP_DWELL"
echo "  DP_CYCLE=$DP_CYCLE  WARMUP=$WARMUP  SIM=$SIM  CINTERVAL=$CINTERVAL"
echo
echo "Sweep:"
echo "  SCALE_LIST=$SCALE_LIST   (load axis: table is regenerated per value)"
echo "  SEL_LIST=$SEL_LIST  BUFFER_LIST=$BUFFER_LIST  SEEDS=$SEEDS"
echo "  PACKET_SIZE=$PACKET_SIZE  JOBS=$JOBS"
echo

[[ -x "$BIN" ]] || { echo "ERROR: noxim binary not found at $BIN (run make)"; exit 1; }
[[ -f "$CONVERTER" ]] || { echo "ERROR: converter not found at $CONVERTER"; exit 1; }

mkdir -p "$OUTDIR/logs" "$OUTDIR/rows" "$TABLE_DIR"
find "$OUTDIR/rows" -maxdepth 1 -name '*.row' -delete 2>/dev/null || true

CSV="$OUTDIR/summary.csv"
MEAN_CSV="$OUTDIR/summary_mean.csv"
COMPARE_CSV="$OUTDIR/summary_compare.csv"

# Filename for a given load scale. Every scale gets its own table so the
# parallel jobs each read a private file and never race.
table_for() { echo "$TABLE_DIR/dnn_ls${1}.txt"; }
export -f table_for
export TABLE_DIR

# ------------------------------------------------------------
# Phase 1 -- generate one table per load scale (sequential, seconds).
# Must complete before any job launches: a job reading a half-written table
# would load a truncated row set and silently under-inject.
# ------------------------------------------------------------
echo "Generating tables:"
for scale in $SCALE_LIST; do
    tbl=$(table_for "$scale")
    stem=$(basename "$tbl" .txt)
    if ! DNN_LOAD_SCALE="$scale" \
         DNN_TABLE_DIR="$TABLE_DIR" \
         DNN_TABLE_STEM="$stem" \
         WARMUP_DP_CYCLES="$WARMUP_DP_CYCLES" \
         SIM_DP_CYCLES="$SIM_DP_CYCLES" \
         "$PYTHON" "$CONVERTER" > "$TABLE_DIR/${stem}.gen.log" 2>&1
    then
        echo "  FAILED to generate scale=$scale -- see $TABLE_DIR/${stem}.gen.log"
        sed -n '/ERROR/p' "$TABLE_DIR/${stem}.gen.log" | sed 's/^/    /'
        exit 1
    fi

    # The converter's placement boxes are hardcoded for one mesh. Verify the
    # emitted table matches the mesh we are about to simulate, rather than
    # trusting that DIMX/DIMY/DIMZ here and in the converter agree.
    want="mesh ${DIMX}x${DIMY}x${DIMZ}"
    if ! grep -q "$want" "$tbl"; then
        echo "  ERROR: $tbl was not generated for $want"
        grep -m1 '^% ' "$tbl" | sed 's/^/    header: /'
        exit 1
    fi

    rows=$(grep -vc '^%' "$tbl" || true)
    maxpir=$(grep -v '^%' "$tbl" | awk '{s[$1]+=$3} END {m=0; for (k in s) if (s[k]>m) m=s[k]; printf "%.4f", m}')
    echo "  scale=$scale  rows=$rows  max_cumulative_pir~$maxpir  -> $tbl"
done
echo

extract_metric() {
    local pattern="$1"
    local file="$2"
    grep -iE "$pattern" "$file" \
        | tail -1 \
        | grep -Eo '[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?' \
        | tail -1 || true
}

# One grid point. Writes a single CSV row to its own file (no shared-file race).
run_one() {
    local buffer="$1" sel="$2" scale="$3" seed="$4"
    local tag="buf_${buffer}_sel_${sel}_ls_${scale}_seed_${seed}"
    local log="$OUTDIR/logs/${tag}.log"
    local row="$OUTDIR/rows/${tag}.row"
    local tbl
    tbl=$(table_for "$scale")

    # -traffic and the filename are SEPARATE arguments -- see header note 1.
    # -pir is deliberately omitted: it is ignored in table mode (header note 2),
    # so passing it would only imply a control that does not exist.
    #
    # -samp 1 CORRECTS THE PER-IP THROUGHPUT DENOMINATOR.  TGlobalStats.cpp:280
    # computes  total_cycles = simulation_time * no_of_samples - warmup,  which is
    # right for main_multi_step.cpp (it loops over samples) but WRONG for main.cpp,
    # which calls sc_start(simulation_time) once -- see its "This now run once
    # only" comment.  At the default no_of_samples = 10 the denominator is ~10x too
    # large, so "% Throughput (flits/cycle/IP)" (line 341, the value extract_metric
    # picks up) reads ~10x LOW.  "% Global average throughput" (line 340) uses a
    # different path and was always correct.
    #
    # Safe: under main.cpp, no_of_samples only affects this denominator, the
    # cosmetic "Now running for N cycles" banner (also 10x overstated without it),
    # and showStats2(), which is unused.  Thermal management is off (mode 0).
    #
    # !! Results produced BEFORE this flag have per-IP throughput ~10x low.  To
    # compare against them, scale the old values by
    #     (SIM * 10 - WARMUP) / (SIM - WARMUP)
    # or re-run.  DP-vs-BL ratios are unaffected -- the factor cancels.
    if ! "$BIN" \
        -dimx "$DIMX" -dimy "$DIMY" -dimz "$DIMZ" \
        -buffer "$buffer" \
        -routing "$ROUTING" \
        -sel "$sel" \
        -size "$PACKET_SIZE" "$PACKET_SIZE" \
        -cinterval "$CINTERVAL" \
        -warmup "$WARMUP" \
        -sim "$SIM" \
        -samp 1 \
        -traffic table "$tbl" \
        -seed "$seed" \
        > "$log" 2>&1
    then
        echo "$buffer,$sel,$scale,$seed,ERROR,ERROR,ERROR,ERROR,ERROR,$log" > "$row"
        echo "  FAILED: $tag"
        return 0
    fi

    local avg_delay avg_throughput total_received total_sent total_energy
    avg_delay=$(extract_metric "average.*delay|avg.*delay|global.*delay|packet.*delay" "$log")
    avg_throughput=$(extract_metric "average.*throughput|avg.*throughput|throughput" "$log")
    total_received=$(extract_metric "received.*packets|total.*received|received" "$log")
    total_sent=$(extract_metric "sent.*packets|total.*sent|sent" "$log")
    total_energy=$(extract_metric "total.*energy|energy" "$log")

    echo "$buffer,$sel,$scale,$seed,${avg_delay:-NA},${avg_throughput:-NA},${total_received:-NA},${total_sent:-NA},${total_energy:-NA},$log" > "$row"
    echo "  done: $tag"
}

export -f run_one extract_metric
export BIN DIMX DIMY DIMZ ROUTING CINTERVAL WARMUP SIM OUTDIR PACKET_SIZE

# ------------------------------------------------------------
# Phase 2 -- run the grid, JOBS at a time.
# ------------------------------------------------------------
{
    for buffer in $BUFFER_LIST; do
        for scale in $SCALE_LIST; do
            for seed in $SEEDS; do
                for sel in $SEL_LIST; do
                    echo "$buffer $sel $scale $seed"
                done
            done
        done
    done
} | xargs -P "$JOBS" -n 4 bash -c 'run_one "$@"' _

# ------------------------------------------------------------
# Assemble summary.csv from the per-job row files (deterministic order).
# ------------------------------------------------------------
{
    echo "buffer,selection,load_scale,seed,avg_delay,avg_throughput,total_received,total_sent,total_energy,raw_log"
    cat "$OUTDIR/rows/"*.row | sort -t, -k1,1n -k2,2 -k3,3n -k4,4n
} > "$CSV"

echo
echo "Done."
echo "Raw logs: $OUTDIR/logs"
echo "Tables:   $TABLE_DIR"
echo "CSV:      $CSV"

# ------------------------------------------------------------
# Mean over seeds.
# ------------------------------------------------------------
{
    echo "buffer,selection,load_scale,mean_avg_delay,mean_avg_throughput,mean_total_energy,n"
    awk -F, '
    NR==1 { next }
    $5 != "NA" && $5 != "ERROR" {
        key=$1 "," $2 "," $3
        delay_sum[key]+=$5
        thr_sum[key]+=$6
        energy_sum[key]+=$9
        n[key]++
    }
    END {
        for (key in n) {
            split(key,a,",")
            print a[1] "," a[2] "," a[3] "," delay_sum[key]/n[key] "," thr_sum[key]/n[key] "," energy_sum[key]/n[key] "," n[key]
        }
    }
    ' "$CSV" | sort -t, -k1,1n -k2,2 -k3,3n
} > "$MEAN_CSV"

echo "Mean CSV: $MEAN_CSV"

# ------------------------------------------------------------
# Paired DP-vs-bufferlevel comparison by buffer and load scale.
# ------------------------------------------------------------
{
    echo "buffer,load_scale,bufferlevel_delay,dp_delay,dp_delay_reduction_pct,bufferlevel_throughput,dp_throughput,bufferlevel_energy,dp_energy"
    awk -F, '
    NR==1 { next }
    {
        key=$1 "," $3
        sel=$2
        delay[key,sel]=$4
        thr[key,sel]=$5
        energy[key,sel]=$6
        seen[key]=1
    }
    END {
        for (key in seen) {
            bld=delay[key,"bufferlevel"]
            dpd=delay[key,"dp"]
            blt=thr[key,"bufferlevel"]
            dpt=thr[key,"dp"]
            ble=energy[key,"bufferlevel"]
            dpe=energy[key,"dp"]
            if (bld != "" && dpd != "" && bld > 0) {
                split(key,a,",")
                reduction=(bld-dpd)/bld*100.0
                print a[1] "," a[2] "," bld "," dpd "," reduction "," blt "," dpt "," ble "," dpe
            }
        }
    }
    ' "$MEAN_CSV" | sort -t, -k1,1n -k2,2n
} > "$COMPARE_CSV"

echo "Compare CSV: $COMPARE_CSV"
echo
echo "NOTE: the load axis is load_scale, not pir -- -pir is inert under a"
echo "      traffic table. Quote absolute delay alongside DP-vs-BL %, and"
echo "      locate this pattern's OWN knee before trusting a reduction %"
echo "      (FINDINGS.md routing-variant study)."
