# Release checklist (replication_repo → GitHub + Zenodo)

Updated 2026-09-01 (CORRECTIONS N91). Everything below the line is the build-site log kept for provenance.

## Done
- [x] Result CSVs are the five-seed set (N85 promotion; `analysis/results_3seed_archive/` keeps the displaced three-seed files locally, not in git).
- [x] §5.2 partition axis on draws {1..5}; all 102 partition caches, 397 head logs, 116 rule books in `data/derived/` with `data/checksums/manifest.csv` (579 files, 0 mismatches).
- [x] Nine audit gates pass at the shipped root; the gates read the manuscript snapshot in `paper/` (`CSA_MANUSCRIPT_DIR` overrides).
- [x] No hard-coded workstation paths in the code path a reader runs (`CSA_*` variables; `slurm/` and the legacy defaults in `rule_engine/p1_inversion/p1_lib.py` are provenance only).
- [x] Misleading names removed: `turnover_v3_3seed_mean` → `turnover_v3_mean`, `peer_spanning_v3_3seed` → `peer_spanning_v3` (CSV, producer, consumers).
- [x] `.gitignore` (derived data, scratch, logs), `README.md`, `LICENSE` (draft), `data/LICENSE-DATA.md` (draft), `CITATION.cff` (draft), CI workflow.

## Owed before the repository goes public
- [x] Author list and order: Lunji Zhu (UCLA); Yixuan He (Arizona State University); Mihai Cucuringu (UCLA, Oxford) — in `CITATION.cff` and the `LICENSE` copyright line (2026-09-01).
- [x] Licences confirmed by the user 2026-09-01: code MIT (`LICENSE`), data CC BY 4.0 (`data/LICENSE-DATA.md`). GICS: the `gics` partition cache ships in place of the classification (Mihai to object if needed).
- [x] Repository `lzwbh/clustering-statarb-replication` created 2026-09-01; `git init` inside `replication_repo/` (nested in the parent `GNN_for_Trading` tree, which does not track it); first commit made, push by the user.
- [x] Zenodo record published 2026-09-01: https://doi.org/10.5281/zenodo.22241254 (7 files, 2.9 GB compressed: 5 tarballs + MANIFEST.csv + SHA256SUMS; CC BY 4.0). DOI in README and CITATION.cff; Data Availability Statement in main.tex is Refine's.
- [ ] **paper/ re-snapshot at the submitted tag** (`make paper-sync`), then rerun `make audit`.
- [x] Deleted on the user's word (2026-09-01): `analysis/results_5seed/`, `TODO.md`, `audit/verify_printed.py.bak_5seed_k1span`, the superseded `fig_ff_curve` script/PDF/preview.

---
# Build-site TODO (replication_repo)

Done (2026-08-29 night): analysis/{spanning,turnover,strev_spanning,split,select_ci,era_ratios,peer_spanning_v3,mc_size,serial_dep}_v3.py rewritten (serial_dep `size` column awaits the user: 4-seed vs legacy 5-file glob) (shared analysis/_compare.py) on the shared modules and reproducing the shipped CSVs (1e-14 / 1e-8); layout; paths.py; README skeleton; analysis/{books,factors,common_calendar}.py; audit/{verify_printed.py (74 checks, 0 FAIL in-repo), producers.yaml, ledger, CORRECTIONS.md, README}; tools/checksums.py; data/fetch_ken_french.py; figures/scripts/* rewritten on the shared loader (9/9; text identical to the manuscript figures); analysis/print_tables.py; data/derived populated (rule books, 160 head logs, 42 position files, factors).

Next:
1. producers_raw: DELETED 2026-08-30 after a four-gate audit (byte-identical originals in server_package; all 34 static+dynamic outputs covered by clean producers; fast chain rerun ALL OK; conventions carried into docstrings). All 29 producers clean.
2. analysis/run_all.py: DONE (fast chain ALL PRODUCERS OK; --slow tier = MC x4 + turnover, serial_dep after).
3. rule_engine/: DONE — full L2 rebuild inside the repo: 76/76 rule books reproduce (68 byte-identical; the 8 tier-2 partition-seed twins identical on every common day, now shipped on the full 6,943-day frame; CORRECTIONS N81 add. 3). partitions/ + head/: paths shimmed, READMEs, run_head.py wrapper; pipeline_work.py untouched (md5 0b87d7baeb2b).
4. tab:sizes / tab:ksweep: DONE (analysis/sizes_from_caches.py, analysis/ksweep_v3.py; all 56+15 cells reproduce; harness now 76 checks).
5. data/: DONE — README, panel_checksums.json, build_panel.py (CRSP→returns/caps/mask, from recleaning/build_cleaned_v3.py), panel_acceptance.py, DATA_CLEANING_NOTES.md, build_compat_panel.py (BASE env still points at the old machine; wrap with paths).
6. tools/check_weights.py: DONE (every-day reconstruction of all 42 runs; see run below).
7. CI workflow: DONE (.github/workflows/verify.yml runs verify_printed + print_tables on environment/requirements-l0.txt).
8. paper/: sources snapshotted (re-copy at the submitted tag). CITATION.cff and LICENSE files wait for the user (author list, licences).
9. Zenodo: tools/package_zenodo.py written (dry run: 3.58 GB with the 42 main weight files; 76 rule books incl. sigw30, 160 head logs, 62 partition caches, 46 result CSVs).

Decisions settled 2026-08-30: Zenodo weights = 42 main + 2 peer; extras/ deferred to after the
release (repo ships without exploratory results). Still owed: repo name/org & public timing;
licences (code MIT / data CC BY 4.0 proposed; GICS shareability via Mihai).

2026-08-30 afternoon: nine-figure restyle batch (user-approved list via Refine) done in the masters
and installed in JFEC_OUP (printed font >=7pt everywhere, content edits per list); repo copies ported: 9/9 token-identical (select re-ported after the xlabel fix; spot-checked). New producer analysis/joint_spanning_v3.py
(N82): joint FF5+MOM+ST_Rev+5PC spec, all 28 books stay significant (min |t| 2.56, rule K=1).

Seed-extension analysers, all verified against the published three-seed values before the new runs
land: analysis/seed_extension_v3.py (per-arm mps/sd/seed-averaged Sharpe + FF6 alpha, NE-gated),
analysis/field_ruler_stats_v3.py (pooled sd 0.0844 / 24 df / CI [0.066,0.117] / gap counts 5-7-10),
analysis/seed_dependent_values_v3.py (§4.1 17.0%/24.7% and 5-of-12 / 12-of-12, §4.3 75.3%/68.4%,
§4.4 +0.13 sd 0.24 t 0.94, A.3 -0.27 p 0.39), tools/ingest_head_runs.py (gate + calendar + copy).

## Resolved 2026-09-01 (N85, promoted to five seeds) — kept as written for the record: the shipped result CSVs were a three-seed snapshot

`analysis/results/*.csv` were built against head seeds `{42, 1, 123}`; the manuscript is now on
`{1, 2, 3, 4, 5}`. `analysis/_compare.py` writes a shipped file only when the fresh computation
reproduces it, so no producer can refresh them and every seed-dependent one prints
`NOT written (mismatch)`. Concretely: `perrule_count_v3` gives 4/12 and 7/12 at five seeds, which is
what Section 4.1 prints, while the shipped CSV holds the three-seed 5/12 and 12/12.

The decision is not mine to take, because it costs the package its current acceptance anchor:

* **Refresh** — add a deliberate `--refresh` path, regenerate at five seeds. The package then
  reproduces the paper end to end. But "the producer reproduces the shipped CSV" stops being a test
  (it becomes a tautology), so the anchor has to move to "the CSV reproduces the printed value",
  which is what `audit/verify_printed.py` already does for the 78 printed quantities.
* **Keep and document** — leave the three-seed snapshot, and say in the README that L1 reproduces the
  build-site CSVs rather than the paper's numbers. Cheaper, but a referee who runs L1 and compares
  with a table will find a mismatch and has to read a paragraph to learn it is expected.

Refresh is the better end state; the question is whether it happens before or after submission.
