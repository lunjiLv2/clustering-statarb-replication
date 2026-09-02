#!/bin/bash
#SBATCH --job-name=repo_pos5
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/positions_5seed.log
# Five-seed rerun of the three position producers that still read the OLD head-seed set in the shipped CSVs
# (gradient_pos_v3 -> tab:gradient position row; pos_overlap_v3 + peerdist_v3 -> A.13 app:peerdist).
# Writes ONLY into analysis/results_5seed/ (CSA_RESULTS_ROOT); the shipped analysis/results/ is never touched
# (compare_and_write refuses CSA_FORCE_WRITE there). peerdist_v3 prints only. ari_across_rule_v3 is partition-only
# (no head seed) and is not rerun. The login node's 10 GB cap OOM-killed pos_overlap at 60 gated frames (2026-09-01).
set -u
cd /home/lunjizhu/gnn_ws/replication_repo; PY=/home/lunjizhu/.venv/bin/python
export CSA_PANEL_ROOT=/home/lunjizhu/Cleaned_Data_v3_compat OMP_NUM_THREADS=4
export CSA_RESULTS_ROOT=/home/lunjizhu/gnn_ws/replication_repo/analysis/results_5seed CSA_FORCE_WRITE=1
echo "seeds: $($PY -c 'import paths; print(paths.SEEDS)')"
for s in pos_overlap_v3 peerdist_v3 gradient_pos_v3; do
  echo "=== $s $(date +%T)"; $PY -u analysis/$s.py || echo "$s FAILED rc=$?"; echo "--- $s end $(date +%T)"
done
echo "REPO POS5 DONE $(date +%T)"
