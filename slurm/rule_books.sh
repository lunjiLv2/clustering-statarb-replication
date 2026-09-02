#!/bin/bash
#SBATCH --job-name=repo_rulebooks
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/rule_books.log
# Layer-L2 check: rebuild every rule book inside the repository layout and byte-compare with data/derived/rule_books.
set -u
cd /home/lunjizhu/gnn_ws/replication_repo; PY=/home/lunjizhu/gnn_ws/server_package/_sol_base/.venv/bin/python
export CSA_PANEL_ROOT=/home/lunjizhu/Cleaned_Data_v3_compat OMP_NUM_THREADS=4
R=runs/rule_books_rebuild
echo "=== main 54 arms $(date +%T)"
(cd rule_engine && $PY -u run_naive_routeA.py --parts v3 --basis raw --date-start 1997-05-23 --date-end 2024-12-30 \
    --dump-daily ../$R/main --out ../$R/naive_routeA_v3_raw.csv) || echo "MAIN RUN FAILED rc=$?"
echo "=== sigw30 14 arms $(date +%T)"
(cd rule_engine && $PY -u run_naive_routeA.py --parts v3 --basis raw --sig-w 30 --date-start 1997-05-23 --date-end 2024-12-30 \
    --only kmeans_ret pca_load agglo_avg agglo_complete spectral_unsigned gics sponge_w60 fv2a_w60 fv3sm_w60 sortino_w60 sharpe_fixed_w60 sssnetpre k1 random \
    --dump-daily ../$R/sigw30 --out ../$R/naive_routeA_v3_raw_sigw30.csv) || echo "SIGW30 RUN FAILED rc=$?"
echo "=== compare $(date +%T)"
same=0; diff=0; miss=0
for f in data/derived/rule_books/*.csv; do b=$(basename $f .csv)
  case $b in *_sigw30) g=$R/sigw30/${b%_sigw30}.csv;; *) g=$R/main/$b.csv;; esac
  if [ ! -f "$g" ]; then echo "MISSING $b"; miss=$((miss+1)); elif cmp -s "$f" "$g"; then same=$((same+1)); else echo "DIFF $b"; diff=$((diff+1)); fi
done
echo "RULE BOOKS: identical $same  differ $diff  missing $miss"
echo "REPO RULEBOOKS DONE $(date +%T)"
