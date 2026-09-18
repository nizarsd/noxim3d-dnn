#!/bin/bash
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/topn/matrix
until grep -q "B2 DONE" $K/campaign_b2.log 2>/dev/null; do sleep 120; done
python3 $K/phase6_minE.py >> $K/campaign_minE.log 2>&1 || exit 1
bash $K/run_minE.bash
