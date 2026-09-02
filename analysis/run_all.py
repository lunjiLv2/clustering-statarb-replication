"""Layer L1: regenerate every result CSV from the shipped books and compare with analysis/results.

Each producer key-merges its output with the shipped CSV and prints the number of rows matched and
the maximum absolute difference; a producer overwrites the shipped file only when it reproduces it.
The order below respects the dependencies (split reads peer_spanning; serial_dep reads mc_size).

    python analysis/run_all.py            # fast producers (minutes)
    python analysis/run_all.py --slow     # also the Monte Carlo, turnover, positions/partitions and lens producers
                                          # (needs CSA_PANEL_ROOT; ~2 h on one node, or use the slurm/ scripts)
"""
from __future__ import annotations
import subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAST = ["spanning_v3", "strev_spanning_v3", "select_ci_v3", "era_ratios_v3", "peer_spanning_v3", "split_v3",
        "sizes_from_caches", "ksweep_v3", "perrule_count_v3", "formal_v3", "lm_boot_v3"]
SLOW = [("mc_size_v3", ["--B", "5000", "--seed", s]) for s in ("42", "7", "101", "2024")] + [("turnover_v3", []), ("formal_v3", ["--controls"]),
        ("naive_turnover_v3", []), ("ari_within_rule_v3", []), ("ari_across_rule_v3", []), ("gradient_pos_v3", []), ("pos_overlap_v3", []),
        ("vshare_v3", []), ("vshare_v3_nosingleton", []), ("dose_v3_traded", []), ("verify_lens", []), ("lens_extras_v3", []),
        ("peer_lens_v3_cal6913", []), ("pc_factors_v3", []), ("beta_lag1_check", []), ("pos_autocorr_naive", [])]
AFTER_SLOW = ["serial_dep_v3"]


def run(name: str, args: list[str]) -> bool:
    t = time.time(); print(f"\n=== {name} {' '.join(args)}", flush=True)
    rc = subprocess.call([sys.executable, str(HERE / f"{name}.py"), *args])
    print(f"--- {name}: rc={rc} in {time.time() - t:.0f}s", flush=True); return rc == 0


def main() -> int:
    slow = "--slow" in sys.argv; failed = []
    for n in FAST:
        failed += [] if run(n, []) else [n]
    if slow:
        for n, a in SLOW:
            failed += [] if run(n, a) else [n]
        for n in AFTER_SLOW:
            failed += [] if run(n, []) else [n]
    print("\nALL PRODUCERS OK" if not failed else f"\nFAILED: {failed}"); return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
