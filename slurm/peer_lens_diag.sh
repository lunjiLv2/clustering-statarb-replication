#!/bin/bash
#SBATCH --job-name=repo_peerdiag
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/peer_lens_diag.log
# Diagnostic rerun of the peer lens: full-precision table to the scratchpad, shipped file untouched.
cd /home/lunjizhu/gnn_ws/replication_repo; export CSA_PANEL_ROOT=/home/lunjizhu/Cleaned_Data_v3_compat OMP_NUM_THREADS=8
/home/lunjizhu/gnn_ws/server_package/_sol_base/.venv/bin/python -u analysis/peer_lens_v3_cal6913.py --out runs/peer_lens_diag.csv || echo "TASK FAILED rc=$?"
echo "PEERDIAG DONE $(date +%T)"
