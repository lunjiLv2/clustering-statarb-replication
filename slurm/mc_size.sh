#!/bin/bash
#SBATCH --job-name=repo_mc
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --array=0-3
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/mc_size_%a.log
# The four master seeds of the Monte Carlo size study (analysis/mc_size_v3.py), one task each.
SEEDS=(42 7 101 2024); cd /home/lunjizhu/gnn_ws/replication_repo; export OMP_NUM_THREADS=2
echo "=== seed ${SEEDS[$SLURM_ARRAY_TASK_ID]} $(date +%T)"
../server_package/_sol_base/.venv/bin/python analysis/mc_size_v3.py --B 5000 --seed ${SEEDS[$SLURM_ARRAY_TASK_ID]}
echo "MC DONE $(date +%T)"
