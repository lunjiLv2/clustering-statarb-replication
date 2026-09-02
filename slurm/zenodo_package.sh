#!/bin/bash
#SBATCH --job-name=zenodo_pkg
#SBATCH --partition=general
#SBATCH --qos=grp_yixuanh2
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=/home/lunjizhu/gnn_ws/replication_repo/slurm/zenodo_package.log
# Package the derived data for the Zenodo record (user-approved 2026-09-01): one tar.gz per folder + MANIFEST.csv,
# weights = the main runs + the two peer books (decision 2026-08-30). Output: runs/zenodo_out/ (git-ignored).
set -u
cd /home/lunjizhu/gnn_ws/replication_repo
echo "=== zenodo package $(date +%T)"; /home/lunjizhu/.venv/bin/python tools/package_zenodo.py --out runs/zenodo_out || echo "PACKAGE FAILED rc=$?"
ls -la runs/zenodo_out; sha256sum runs/zenodo_out/*.tar.gz > runs/zenodo_out/SHA256SUMS; echo "=== done $(date +%T)"
