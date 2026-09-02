#!/bin/bash
#SBATCH --job-name=repo_rb_ps5
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:30:00
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/rule_books_ps5.log
# Rule books for the 40 new partition-seed twins (10 arms x partition seeds 2-5; 2026-09-01, the
# sec:pseed basis moves from {42,1,123} to {1,2,3,4,5}). Same engine call as rule_books.sh; output goes to
# runs/rule_books_ps5/ and is copied into data/derived/rule_books/ by hand after inspection (never overwrites).
set -u
cd /home/lunjizhu/gnn_ws/replication_repo; PY=/home/lunjizhu/gnn_ws/server_package/_sol_base/.venv/bin/python
export CSA_PANEL_ROOT=/home/lunjizhu/Cleaned_Data_v3_compat OMP_NUM_THREADS=4
R=runs/rule_books_ps5; mkdir -p $R
echo "=== 40 ps2-5 arms $(date +%T)"
(cd rule_engine && $PY -u run_naive_routeA.py --parts v3 --basis raw --date-start 1997-05-23 --date-end 2024-12-30 \
    --only kmeans_ret_ps2 pca_load_ps2 random_ps2 spectral_unsigned_ps2 sponge_w60_ps2 sssnetpre_ps2 fv2a_w60_ps2 fv3sm_w60_ps2 sharpe_fixed_w60_ps2 sortino_w60_ps2 kmeans_ret_ps3 pca_load_ps3 random_ps3 spectral_unsigned_ps3 sponge_w60_ps3 sssnetpre_ps3 fv2a_w60_ps3 fv3sm_w60_ps3 sharpe_fixed_w60_ps3 sortino_w60_ps3 kmeans_ret_ps4 pca_load_ps4 random_ps4 spectral_unsigned_ps4 sponge_w60_ps4 sssnetpre_ps4 fv2a_w60_ps4 fv3sm_w60_ps4 sharpe_fixed_w60_ps4 sortino_w60_ps4 kmeans_ret_ps5 pca_load_ps5 random_ps5 spectral_unsigned_ps5 sponge_w60_ps5 sssnetpre_ps5 fv2a_w60_ps5 fv3sm_w60_ps5 sharpe_fixed_w60_ps5 sortino_w60_ps5  \
    --dump-daily ../$R --out ../$R/naive_routeA_v3_raw_ps5.csv) || echo "PS5 RUN FAILED rc=$?"
ls $R/*.csv | wc -l
echo "REPO RULEBOOKS PS5 DONE $(date +%T)"
