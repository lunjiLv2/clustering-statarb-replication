# Provenance and verification

* `verify_printed.py` — 78 checks that recompute the manuscript's headline numbers from the shipped
  result CSVs (and, with `--slow`, cross-check the Newey–West kernel against statsmodels). `0 FAIL` is
  the release condition; CI runs it on every commit.
* `AUDIT_LEDGER_2026-08-29_n204.csv` — one row per numeric token of the submitted render: location,
  claim, source file, recomputation method, value under the printed and the alternative convention,
  verdict, reproduction command.
* `CORRECTIONS.md` — the error ledger of the project: every superseded number, why it was wrong, and
  what replaced it. Read it before quoting anything from an older draft.
* `producers.yaml` — the map from every exhibit to the script that produces it, its inputs and its
  output CSV (the allow-list that decides what is in this repository).

Conventions that a reader must know to reproduce the numbers are stated in `analysis/books.py`
(payoff series, Sharpe, mean-of-per-seed vs seed-averaged) and `analysis/factors.py` (factor files,
calendar shift, Newey–West lag).

## How the build site was verified (2026-08-29/30)

Every layer was checked against the artefacts that produced the submitted manuscript, from inside
this repository's own layout (its `paths.py`, its copies of the data):

* **L0** — `verify_printed.py` 0 FAIL; the nine figure scripts redrawn and their PDF text layers
  compared token-for-token with the submitted figures (all identical); `analysis/print_tables.py`
  bands compared with the tables.
* **L1** — every producer in `analysis/` ends with a key-merge against the shipped CSV
  (`analysis/_compare.py`) and reports rows matched and the maximum absolute difference; the
  shipped file is overwritten only when the difference is below 1e-6 (the largest observed is 6e-8,
  a CSV float round-trip; Monte Carlo counts are exact). `tools/check_weights.py` reconstructs the
  logged daily P&L of all 42 main runs from the shipped positions on every day (max 2e-9).
* **L2** — `slurm/rule_books.sh` rebuilt all 76 rule books from the partition caches and the panel:
  68 byte-identical, 8 identical on every common day (CORRECTIONS N81 addendum 3); one rule book
  takes 30 s. The panel used for the paper is pinned by `data/panel_checksums.json`.
* **L3** — not re-run (GPU, ~1.5 h per run); the executed pipeline is shipped unmodified with the
  run manifests, and `head/README.md` documents the environment contract.
