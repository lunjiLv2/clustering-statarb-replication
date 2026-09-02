#!/bin/bash
#SBATCH --job-name=repo_figs
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:00:00
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/figures_heavy.log
# The two figures that need the bootstrap (select_vs_ew) or the position files (bet_corr).
cd /home/lunjizhu/gnn_ws/replication_repo; PY=../server_package/_sol_base/.venv/bin/python; export OMP_NUM_THREADS=8
for s in fig_select_vs_ew_v3 fig_bet_corr_v3; do echo "=== $s $(date +%T)"; $PY figures/scripts/$s.py; done; echo "REPO FIGS DONE $(date +%T)"
