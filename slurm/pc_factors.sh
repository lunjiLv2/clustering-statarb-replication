#!/bin/bash
#SBATCH --job-name=repo_pcfactors
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/pc_factors.log
# Layer-L1 check of the principal-component factor construction (analysis/pc_factors_v3.py, ~20 min):
# rebuilds the five daily PC factors from the compat panel and compares them with the shipped file.
cd /home/lunjizhu/gnn_ws/replication_repo; export OMP_NUM_THREADS=4 CSA_PANEL_ROOT=/home/lunjizhu/Cleaned_Data_v3_compat
echo "=== pc_factors $(date +%T)"
../server_package/_sol_base/.venv/bin/python analysis/pc_factors_v3.py || echo "PC FACTORS FAILED rc=$?"
echo "PC DONE $(date +%T)"
