#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-verify}"
cd "$ROOT/research"
export PYTHONPATH=.:scripts
export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/aidash_mpl}"

case "$MODE" in
  verify)
    python3 scripts/verify_arima_lstm_thesis_results.py
    python3 scripts/verify_arima_lstm_advanced_results.py
    ;;
  primary)
    python3 scripts/run_arima_lstm_thesis_study.py
    python3 scripts/verify_arima_lstm_thesis_results.py
    ;;
  advanced)
    python3 scripts/run_arima_lstm_advanced_study.py
    python3 scripts/verify_arima_lstm_advanced_results.py
    ;;
  all)
    python3 scripts/run_arima_lstm_thesis_study.py
    python3 scripts/verify_arima_lstm_thesis_results.py
    python3 scripts/run_arima_lstm_advanced_study.py
    python3 scripts/verify_arima_lstm_advanced_results.py
    ;;
  *)
    echo "Usage: $0 [verify|primary|advanced|all]" >&2
    exit 2
    ;;
esac
