# Replication package — entry points. See README.md for what each layer needs.
PY ?= python
.PHONY: verify tables figures analysis audit checksums factors paper-sync
verify:            ## L0: the printed-number harness against the shipped result CSVs
	$(PY) audit/verify_printed.py
tables:            ## L0: print every table's cells from analysis/results (no LaTeX needed)
	$(PY) analysis/print_tables.py
factors:           ## L0: fetch the Ken French factor files into data/factors/
	$(PY) data/fetch_ken_french.py
figures:           ## L0/L1: redraw every figure into paper/figures (3 of the 10 manuscript figures need data/derived)
	for s in figures/scripts/fig_*_v3.py; do $(PY) $$s; done
analysis:          ## L1: rebuild analysis/results from the daily books (needs data/derived)
	$(PY) analysis/run_all.py
audit:             ## L1: every gate in audit/ (verify_printed and the seed-language scan run without data)
	$(PY) audit/verify_printed.py
	$(PY) audit/check_seed_language.py
	$(PY) audit/check_calendar_bypass.py
	$(PY) audit/check_printed_5seed.py
	$(PY) audit/check_pseed_5ps.py
	$(PY) audit/check_field_window_5seed.py
	$(PY) audit/check_note_maxw.py
	$(PY) audit/check_pseed_flip_literals.py
	$(PY) audit/fingerprint_3seed.py
	$(PY) audit/check_figures_text.py
checksums:         ## record SHA-256 / row counts / date ranges of every data file
	$(PY) tools/checksums.py write
paper-sync:        ## authors: refresh paper/ from the working manuscript (CSA_MANUSCRIPT_SRC, default ../JFEC_OUP)
	SRC=$${CSA_MANUSCRIPT_SRC:-../JFEC_OUP}; cp $$SRC/sections/0*.tex $$SRC/sections/A_supplementary.tex paper/sections/; \
	cp $$SRC/main.tex $$SRC/refs.bib $$SRC/preamble-oup.tex paper/; \
	for f in paper/figures/*.pdf; do s=$$SRC/figures/$$(basename $$f); [ -f $$s ] && cp $$s paper/figures/ || echo "paper-sync: $$s not in the manuscript yet, kept the repo copy"; done
