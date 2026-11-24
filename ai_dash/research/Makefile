PYTHON ?= python
export PYTHONPATH := .

.PHONY: test controlled trace analyze figures report ai ai-early-warning ai-generalization arima-lstm arima-lstm-advanced simulation-completion portable-host verify-best verify-ai verify-ai-early-warning verify-ai-generalization verify-arima-lstm verify-arima-lstm-advanced verify-simulation-completion verify-host verify-all strongest-reproduce all clean-generated

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

ai:
	MPLCONFIGDIR=/tmp/rtdash_mpl PYTHONPATH=. $(PYTHON) scripts/run_ai_extension_study.py

ai-early-warning:
	MPLCONFIGDIR=/tmp/rtdash_mpl PYTHONPATH=.:scripts $(PYTHON) scripts/run_ai_early_warning_study.py

ai-generalization:
	MPLCONFIGDIR=/tmp/rtdash_mpl PYTHONPATH=. $(PYTHON) scripts/run_ai_generalization_study.py

arima-lstm:
	MPLCONFIGDIR=/tmp/rtdash_mpl PYTHONPATH=. $(PYTHON) scripts/run_arima_lstm_thesis_study.py

arima-lstm-advanced:
	MPLCONFIGDIR=/tmp/rtdash_advanced_mpl PYTHONPATH=.:scripts $(PYTHON) scripts/run_arima_lstm_advanced_study.py

simulation-completion:
	MPLCONFIGDIR=/tmp/rtdash_mpl PYTHONPATH=.:scripts $(PYTHON) scripts/run_simulation_completion_study.py

portable-host:
	PYTHONPATH=. $(PYTHON) scripts/run_portable_host_benchmark.py

verify-best:
	PYTHONPATH=. $(PYTHON) scripts/verify_best_journal_results.py

verify-ai:
	PYTHONPATH=. $(PYTHON) scripts/verify_ai_extension_results.py

verify-ai-early-warning:
	PYTHONPATH=.:scripts $(PYTHON) scripts/verify_ai_early_warning_results.py

verify-host:
	PYTHONPATH=. $(PYTHON) scripts/verify_portable_host_benchmark.py

verify-ai-generalization:
	PYTHONPATH=. $(PYTHON) scripts/verify_ai_generalization_results.py

verify-arima-lstm:
	PYTHONPATH=. $(PYTHON) scripts/verify_arima_lstm_thesis_results.py

verify-arima-lstm-advanced:
	PYTHONPATH=. $(PYTHON) scripts/verify_arima_lstm_advanced_results.py

verify-simulation-completion:
	PYTHONPATH=. $(PYTHON) scripts/verify_simulation_completion_results.py

verify-all: verify-best verify-ai verify-ai-early-warning verify-host verify-simulation-completion verify-ai-generalization verify-arima-lstm verify-arima-lstm-advanced

strongest-reproduce:
	PYTHONPATH=.:scripts $(PYTHON) scripts/run_best_journal_study.py
	$(MAKE) ai
	$(MAKE) ai-early-warning
	$(MAKE) simulation-completion
	$(MAKE) ai-generalization
	$(MAKE) arima-lstm
	$(MAKE) arima-lstm-advanced
	$(MAKE) portable-host
	$(MAKE) verify-all

all: test controlled analyze figures report

clean-generated:
	rm -rf results/batches results/trace_run results/statistics results/figures
