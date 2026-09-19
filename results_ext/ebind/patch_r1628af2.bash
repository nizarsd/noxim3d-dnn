#!/bin/bash
# 8 more ResNet (16,2,8) above-floor placements: probe -> knee rung ->
# BL / DP / DPN@90 (N=23, ci 138) / DPN@95 (N=27, ci 162), 8 seeds.
cd /home/nizar/noxim3d-dnn || exit 1
K=results_ext/ebind
exec >> $K/run_r1628af2.log 2>&1
echo "=== r1628 af2 PATCH start $(date)"
run1(){ # tab pol seed sinks
  local SEL="-sel bufferlevel" TP=""
  [ "$2" = dp ] && SEL="-sel dp -dpcost occupancy -cinterval 648"
  if [ "$2" = hyb ];   then SEL="-sel dp -dpcost occupancy -cinterval 138"; TP="-dptopn 23 $4"; fi
  if [ "$2" = hyb95 ]; then SEL="-sel dp -dpcost occupancy -cinterval 162"; TP="-dptopn 27 $4"; fi
  out=$(timeout 2400 ./noxim -size 16 16 -dimx 6 -dimy 6 -dimz 3 -buffer 16 \
        -routing oddevenbalanced $SEL $TP -warmup 1944 -sim 38536 -seed $3 -traffic table $1 2>/dev/null)
  a=$(echo "$out"|grep -oP "average delay \(cycles\): \K[0-9.]+")
  p=$(echo "$out"|grep -oP "^% Delay p99 \(cycles\): \K[0-9.]+")
  echo "$(basename $1 .txt) $2 $3 ${a:-NA} ${p:-NA}"
}
export -f run1
for kk in 1850 1900 1950 2000 2050; do ls $K/tables_r1628af2/*_k$kk.txt 2>/dev/null; done | xargs -P 14 -n 1 bash -c 'run1 "$0" bl 1' >> $K/probe_r1628af2.txt
echo "=== probe done $(date)"
python3 - <<'PY'
import collections
d=collections.defaultdict(dict)
for ln in open('results_ext/ebind/probe_r1628af2.txt'):
    p=ln.split()
    if p[3]=='NA': continue
    tag,k=p[0].rsplit('_k',1); d[tag][int(k)]=float(p[3])
with open('results_ext/ebind/run_spec_r1628af2.txt','w') as f:
    for tag in sorted(d):
        ks=d[tag]; ff=ks[min(ks)]
        best=min(ks.items(), key=lambda kv: abs(kv[1]/ff-5)); dep=best[1]/ff
        flag='OK' if 4.0<=dep<=6.0 else 'OOB'
        f.write(f"{tag} {best[0]:04d} {dep:.1f} {flag}\n")
        print(f"{tag:12s} k{best[0]/1000:.2f} depth {dep:.1f}x {flag}")
PY
: > $K/res_r1628af2.txt
while read tag k dep flag; do
  for pol in bl dp hyb hyb95; do for s in 1 2 3 4 5 6 7 8; do
    echo "$K/tables_r1628af2/${tag}_k${k}.txt $pol $s $K/sinks_${tag}"
  done; done
done < $K/run_spec_r1628af2.txt | xargs -P 14 -n 4 bash -c 'run1 "$@"' _ >> $K/res_r1628af2.txt
echo "=== runs done $(date)"; wc -l $K/res_r1628af2.txt; grep -c NA $K/res_r1628af2.txt
echo "R1628AF2 PATCH DONE $(date)"
