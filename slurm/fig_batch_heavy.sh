#!/bin/bash
#SBATCH --job-name=fig_batch
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:00:00
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/fig_batch_heavy.log
set -u
PY=/home/lunjizhu/gnn_ws/server_package/_sol_base/.venv/bin/python; export OMP_NUM_THREADS=8
cd /home/lunjizhu/gnn_ws/JFEC_A_Manuscript/_reference
for s in fig_select_vs_ew_v3 fig_bet_corr_v3; do echo "=== $s $(date +%T)"; $PY $s.py || echo "$s FAILED rc=$?"; done
echo "FIG BATCH HEAVY DONE $(date +%T)"
