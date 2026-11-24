PYTHON ?= python
export PYTHONPATH := .

.PHONY: test controlled trace analyze figures report all clean-generated

test:
	$(PYTHON) -m pytest -q

controlled:
	$(PYTHON) scripts/run_batched_experiments.py

trace:
	$(PYTHON) scripts/run_batched_experiments.py --trace

analyze:
	$(PYTHON) scripts/analyze_results.py

figures:
	$(PYTHON) -c "from pathlib import Path; from rt_dash.plotting import plot_controlled; plot_controlled(Path('results/controlled_summary.csv'), Path('results/figures'))"

report:
	$(PYTHON) -c "from pathlib import Path; from rt_dash.report import generate_markdown; generate_markdown(Path('results/controlled_summary.csv'), Path('results/trace_summary.csv'), Path('results/EXPERIMENT_REPORT.md'))"

all: test controlled analyze figures report

clean-generated:
	rm -rf results/batches results/trace_run results/statistics results/figures
