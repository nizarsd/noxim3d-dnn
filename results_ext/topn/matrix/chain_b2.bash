#!/bin/bash
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/topn/matrix
until grep -q "AE DONE" $K/campaign_aE.log 2>/dev/null; do sleep 120; done
python3 $K/phase5_bE2.py >> $K/campaign_b2.log 2>&1 || exit 1
bash $K/run_bE2.bash
