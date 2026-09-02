#!/bin/bash
#SBATCH --job-name=fig_ticks
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/fig_select_ticks.log
set -u
PY=/home/lunjizhu/gnn_ws/server_package/_sol_base/.venv/bin/python; export OMP_NUM_THREADS=8
echo "=== manuscript ref $(date +%T)"; cd /home/lunjizhu/gnn_ws/JFEC_A_Manuscript/_reference && $PY fig_select_vs_ew_v3.py || echo "REF FAILED rc=$?"
echo "=== repo $(date +%T)"; cd /home/lunjizhu/gnn_ws/replication_repo && $PY figures/scripts/fig_select_vs_ew_v3.py || echo "REPO FAILED rc=$?"
echo "FIG TICKS DONE $(date +%T)"
