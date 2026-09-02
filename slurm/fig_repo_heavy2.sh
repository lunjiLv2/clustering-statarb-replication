#!/bin/bash
#SBATCH --job-name=fig_repo2
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:00:00
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/fig_repo_heavy2.log
set -u
cd /home/lunjizhu/gnn_ws/replication_repo; PY=../server_package/_sol_base/.venv/bin/python; export OMP_NUM_THREADS=8
for s in fig_select_vs_ew_v3 fig_bet_corr_v3; do echo "=== $s $(date +%T)"; $PY figures/scripts/$s.py || echo "$s FAILED rc=$?"; done
echo "REPO HEAVY2 DONE $(date +%T)"
