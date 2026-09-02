#!/bin/bash
#SBATCH --job-name=fig_bet
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=00:30:00
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/fig_bet_only.log
PY=/home/lunjizhu/gnn_ws/server_package/_sol_base/.venv/bin/python; export OMP_NUM_THREADS=8
cd /home/lunjizhu/gnn_ws/JFEC_A_Manuscript/_reference && $PY fig_bet_corr_v3.py || echo "BET FAILED rc=$?"
echo "BET DONE $(date +%T)"
