# Cluster scripts (authors' provenance)

These `sbatch` scripts ran the heavy producers and figure batches on the authors' cluster
(`general` partition, 4 CPUs, 32–48 GB, `CSA_PANEL_ROOT` set to the compat panel). Paths inside
them point at the authors' tree and will not resolve elsewhere; they are kept so that every result
in `analysis/results/` can be traced to the exact command that produced it. Their `.log` outputs
are not in git (`.gitignore`). A reader with the Zenodo data runs the same producers directly:
`python analysis/run_all.py --slow`.
