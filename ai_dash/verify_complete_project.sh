#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/research"
export PYTHONPATH=.:scripts

printf '\n[1/10] Python test suite\n'
python3 -m pytest -q

printf '\n[2/10] Deterministic RT-DASH / best-journal evidence\n'
python3 scripts/verify_best_journal_results.py

printf '\n[3/10] Raw-sensor AI extension evidence\n'
python3 scripts/verify_ai_extension_results.py

printf '\n[4/10] Exploratory AI early-warning evidence\n'
python3 scripts/verify_ai_early_warning_results.py

printf '\n[5/10] Portable host benchmark evidence\n'
python3 scripts/verify_portable_host_benchmark.py

printf '\n[6/10] Simulation-completion / stress evidence\n'
python3 scripts/verify_simulation_completion_results.py

printf '\n[7/10] AI temporal generalization evidence\n'
python3 scripts/verify_ai_generalization_results.py

printf '\n[8/10] Primary ARIMA+LSTM Paper-2 evidence\n'
python3 scripts/verify_arima_lstm_thesis_results.py

printf '\n[9/10] Advanced ARIMA+LSTM robustness evidence\n'
python3 scripts/verify_arima_lstm_advanced_results.py

printf '\n[10/10] Independent C++17 Release-build tests\n'
cd "$ROOT"
cmake -S research_cpp -B research_cpp/build_complete -DCMAKE_BUILD_TYPE=Release
cmake --build research_cpp/build_complete -j2
ctest --test-dir research_cpp/build_complete --output-on-failure

printf '\nCOMPLETE PROJECT VERIFICATION: PASS\n'
printf 'Scientific result archives were verified without regeneration or modification.\n'
