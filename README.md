# Quantifying the Contributions of Clustering in Statistical Arbitrage — replication package

**Status: release (2026-09-01).** Code: <https://github.com/lzwbh/clustering-statarb-replication>. Derived data: Zenodo <https://doi.org/10.5281/zenodo.22241254> (CC BY 4.0, 2.9 GB compressed). Every number, table and figure of the manuscript is
reproduced by the code here and checked by the gates in `audit/`. Remaining steps are listed in `RELEASE_CHECKLIST.md`.

The paper trades 12 clusterizers and two controls (no clustering, `k1`; a random partition,
`random`) on 27 years of large US equities under two trading components, a fixed cross-sectional
rule and a neural trading head. Every trained-book statistic averages over **five head seeds
`{1, 2, 3, 4, 5}`** (`paths.SEEDS`); the partition-seed study of §5.2 uses **five partition draws
`{1, 2, 3, 4, 5}`** with the head seed pinned at 42. Everything is computed on one common
calendar of 6,913 trading days (8 July 1997 – 27 December 2024), `analysis/COMMON_CALENDAR_v3.csv`,
which every module loads through `analysis/books.py` and asserts against.

## Four layers of access

| layer | what you need | what you get | command |
|---|---|---|---|
| **L0** | Python 3.11 + `environment/requirements-l0.txt` | every table and figure from the shipped result CSVs (`analysis/results/`, 61 files); the 103-check printed-number harness | `make verify tables` (`make figures` needs L1 data for 3 of the 10 figures) |
| **L1** | + the Zenodo data record [10.5281/zenodo.22241254](https://doi.org/10.5281/zenodo.22241254) (daily books, positions, partitions; see `data/README.md`) | the result CSVs, rebuilt from the daily series; every books-based gate | `make analysis` (`python analysis/run_all.py --slow` adds the Monte Carlo, turnover and position producers) |
| **L2** | + CRSP daily data (licensed) → `data/build_panel.py`, `data/build_compat_panel.py` | the 102 partition caches and the 116 rule-based books | `rule_engine/`, `partitions/` |
| **L3** | + one GPU per run (~1.5 h each) | the trained books: 70 main runs (14 arms × 5 seeds), the partition-seed runs, the variant runs | `head/run_head.py --arm kmeans_ret --seed 1` |

Verified in the build site: L0 103/103 checks; L1 every producer reproduces its shipped CSV to
1e-12 or better; L2 76/76 rule books of the main set reproduce (68 byte-identical, 8 identical on
every common day) and the 40 partition-seed books were built here; L3 is not bit-exact — the same
seed on the same code and GPU moves a Sharpe ratio by up to 0.07 (daily correlation 0.96–0.98),
which the paper reports and which no comparison tighter than that should be asked to pass.

## Quick start (L0)

```bash
pip install -r environment/requirements-l0.txt
python data/fetch_ken_french.py          # FF5, momentum, short-term reversal (Ken French library)
make verify                              # audit/verify_printed.py: 0 FAIL expected (without data/derived, 5 of the 103 checks report SKIP)
make tables                              # analysis/print_tables.py: every table's cells
python audit/check_seed_language.py      # no retired-seed-set leftovers in code or prose
```

With the Zenodo data unpacked into `data/derived/` (or `CSA_DATA_ROOT` pointing at it):

```bash
make analysis                            # rebuild analysis/results/ from the daily books
make figures                             # redraw the 10 figures into paper/figures/
make audit                               # every gate in audit/ (see below)
```

## Repository map

| path | contents |
|---|---|
| `paths.py` | the only place that knows where data lives; every script imports it |
| `analysis/` | one producer per result CSV (`*_v3.py`), the shared loader `books.py` (calendar, Sharpe, positions), `factors.py` (Newey–West spanning), `print_tables.py`, `run_all.py`; `results/` holds the shipped CSVs |
| `audit/` | the gates (next section) and the error ledger `CORRECTIONS.md` (N1–N89), a copy of the authors' ledger |
| `figures/scripts/` | `fig_*_v3.py`, one per figure, all through `books.py` and `style.py`; PNG previews in `figures/previews/` |
| `paper/` | snapshot of the manuscript sources (sections, bibliography, the 10 figures) that the gates read; `make paper-sync` refreshes it from the working manuscript |
| `rule_engine/` | the rule-based trading component (`run_naive_routeA.py`, kernel `p1_inversion/p1_lib.py`), layer L2 |
| `partitions/` | the daily partition generators (`gen_daily_partitions_v3.py`, `gen_sssnet_partitions_w60.py`), layer L2 |
| `head/` | the neural trading head (`run_head.py`) and the validity gate `ne_gate.py`, layer L3 |
| `data/` | panel builders, acceptance tests, the factor fetcher, `checksums/manifest.csv` (SHA-256 of every data file); `derived/` is the Zenodo payload and is not in git |
| `tools/` | checksums, weight-file verification, run provenance, the Zenodo packager, the head-run ingester |
| `slurm/` | the authors' cluster scripts (paths point at the authors' tree; kept for provenance) |
| `environment/` | `requirements-l0.txt` (L0) and `requirements.txt` (the full environment that produced the paper) |

## What the gates guard

Every failure this project has had looked normal: a run that finished, a file that was
well-formed, a number that was plausible. The gates therefore test properties, not exit codes.

| gate | property |
|---|---|
| `audit/verify_printed.py` | every printed value (103 checks) recomputes from the shipped CSVs at the printed rounding |
| `audit/check_printed_5seed.py` | the seed-dependent values recompute from the per-seed books at `paths.SEEDS` (L1) |
| `audit/check_pseed_5ps.py` | §5.2, fig:pseed_flip, A.1, A.2 and the §5.4 partition-range clauses at the five partition draws (L1) |
| `audit/check_field_window_5seed.py` | §5.1 field-ruler and §5.5 window sentences from the per-seed books (L1) |
| `audit/check_note_maxw.py` | two table-note claims measured across runs (max weight; effective K under partition redraws) (L1) |
| `audit/check_pseed_flip_literals.py` | fig:pseed_flip reads the five draws at head seed 42, carries no literals, and the shipped PDF is newer than every input |
| `audit/check_calendar_bypass.py` | no script reads a book off disk except through `books.py` (the 6,944 → 6,913-day truncation happens in one place) |
| `audit/check_seed_language.py` | no hard-coded retired seed set and no "three seeds" prose; deliberate sites carry `# 3seed-ok: <reason>` |
| `audit/fingerprint_3seed.py` | no printed decimal matches a statistic of the retired seed set without also matching the current one (L1) |
| `audit/check_figures_text.py` | every figure script regenerates its figure with the same text layer (labels, ticks, printed numbers) as the shipped PDF in `paper/figures/` (L1) |

`head/ne_gate.py` is the pre-registered validity gate for trained runs (rolling-250 mean |net
exposure| ≤ 0.30 and no one-sided day); `tools/ingest_head_runs.py` applies it before any run
enters `data/derived/`. Weight files are accepted only when they reconstruct the run's own logged
payoff to `max|diff| < 1e-6` (`tools/check_weights.py`), never on a correlation.

## Conventions a reader needs

* **Sharpe ratio** = √252 × mean / sd of daily payoff, no risk-free subtraction. Tables state whether a
  trained cell is the mean of per-seed Sharpe ratios or the Sharpe ratio of the seed-averaged payoff;
  the second is larger by 0.16–0.22.
* **Calendars.** Rule-based books are dated on the signal day and pay the next panel day; trained
  books are dated on the payoff day. `analysis/factors.py` joins the factor file at the right lag for
  each (`shift 0` / `shift 1`); the per-producer docstrings say which.
* **Turnover** is one-way, ½ Σ|w_t − w_{t−1}|, and cost is charged as bps × 2 × turnover.
* **Names.** `sssnetpre` in file names is the manuscript's SSSNET arm (fixed precomputed partition);
  `fv2a_w60` = Sharpe (EW), `fv3sm_w60` = Sharpe (graph), `sharpe_fixed_w60` = Sharpe,
  `sortino_w60` = Sortino; `figures/scripts/style.py` holds the display names.

## Environment variables

| variable | default | meaning |
|---|---|---|
| `CSA_DATA_ROOT` | `data/derived` | where the Zenodo payload is unpacked |
| `CSA_PANEL_ROOT` | unset | the CRSP-derived panel (`prices.pkl`, `caps.pkl`, `mask.pkl`); layers L2–L3 and the position producers |
| `CSA_SEEDS` | `1 2 3 4 5` | head seeds every trained-book statistic averages over |
| `CSA_RESULTS_ROOT` | `analysis/results` | write producers into a side directory (`CSA_FORCE_WRITE=1` to write a non-reproducing result there; the shipped directory is never force-written) |
| `CSA_MANUSCRIPT_DIR` | `paper/` | the LaTeX sources the audit gates read |
| `CSA_FIGURES_DIR` | `paper/figures` | where figure scripts write; the figure gate points it at a temp dir |
| `CSA_CAMPAIGN_ROOT` | unset | the authors' training-campaign tree (ingest and provenance tools only) |
| `CSA_SEED_SCAN_TREES` | unset | extra directories for `check_seed_language.py` |

## Provenance

`audit/CORRECTIONS.md` is the project's error ledger: every superseded number, why it was wrong, and
what replaced it. Entries N83–N89 record the move from three to five head seeds and from three to five
partition draws, with the files each change touched. `data/checksums/manifest.csv` fixes the SHA-256,
row count and date range of every data file the package ships (`python tools/checksums.py check`).

## Licence and citation

Code: MIT (`LICENSE`). Derived data on Zenodo: CC BY 4.0 (`data/LICENSE-DATA.md`). CRSP data and
the GICS snapshot are licensed and not distributed; `data/README.md` says what stands in for them.
Please cite the paper and the Zenodo record 10.5281/zenodo.22241254 (`CITATION.cff`).
