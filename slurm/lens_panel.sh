#!/bin/bash
#SBATCH --job-name=repo_lens
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --array=0-5
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/lens_panel_%a.log
# Layer-L2 producers that need the compat panel: traded-universe removal shares (vshare, both variants),
# the corruption dose curve, the factor lens (stages and extras) and the peer lens. Each task runs one
# producer, which compares its table with the shipped CSV and overwrites it only on reproduction.
cd /home/lunjizhu/gnn_ws/replication_repo
export CSA_PANEL_ROOT=/home/lunjizhu/Cleaned_Data_v3_compat OMP_NUM_THREADS=8
PY=/home/lunjizhu/gnn_ws/server_package/_sol_base/.venv/bin/python
case $SLURM_ARRAY_TASK_ID in
  0) S="analysis/vshare_v3.py --nproc 8"; export OMP_NUM_THREADS=1;;
  1) S="analysis/vshare_v3_nosingleton.py";;
  2) S="analysis/dose_v3_traded.py";;
  3) S="analysis/verify_lens.py";;
  4) S="analysis/lens_extras_v3.py";;
  5) S="analysis/peer_lens_v3_cal6913.py";;
esac
echo "=== task $SLURM_ARRAY_TASK_ID: $S  $(date +%T)"
$PY -u $S || echo "TASK FAILED rc=$?"
echo "LENS TASK $SLURM_ARRAY_TASK_ID DONE $(date +%T)"
