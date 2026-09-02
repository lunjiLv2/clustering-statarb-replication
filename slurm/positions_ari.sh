#!/bin/bash
#SBATCH --job-name=repo_posari
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/positions_ari.log
# Layer-L1 producers that read every position file or every partition cache (tab:gradient, §5, §6.3):
# each one key-merges its output with the shipped CSV and overwrites it only when it reproduces.
set -u
cd /home/lunjizhu/gnn_ws/replication_repo; PY=/home/lunjizhu/gnn_ws/server_package/_sol_base/.venv/bin/python
export CSA_PANEL_ROOT=/home/lunjizhu/Cleaned_Data_v3_compat OMP_NUM_THREADS=4
for s in ari_across_rule_v3 gradient_pos_v3 pos_overlap_v3; do
  echo "=== $s $(date +%T)"; $PY -u analysis/$s.py || echo "$s FAILED rc=$?"; echo "--- $s end $(date +%T)"
done
echo "REPO POSARI DONE $(date +%T)"
