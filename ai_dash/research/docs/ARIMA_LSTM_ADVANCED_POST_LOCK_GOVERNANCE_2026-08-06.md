# ARIMA + LSTM Advanced Post-Lock Governance — 2026-08-06

The advanced ARIMA/LSTM protocol was frozen before its own executions, and all
of its hyperparameters, blend weights and scheduler thresholds are selected
from training/validation data only. However, the final three dates had already
been evaluated and inspected in the earlier locked thesis ARIMA+LSTM study
before the advanced study was designed.

Therefore:

- the original thesis ARIMA+LSTM result remains the primary confirmatory result;
- the advanced model is a post-lock sensitivity/robustness analysis, not a new
  independent held-out confirmation;
- improved advanced metrics may be reported but cannot be used to claim a fresh
  test-set discovery or to replace the locked primary model post hoc;
- degraded advanced metrics remain visible;
- the eight rolling-origin refits add causal temporal robustness evidence but
  share the same source trace and are not eight independent datasets;
- a genuinely new confirmatory comparison of advanced architectures would
  require a new compatible trace/dataset that has not already been inspected.

This governance rule protects the project from repeated-test overclaiming while
still allowing the advanced study to answer mechanism, robustness, ablation and
prediction-fault questions.
