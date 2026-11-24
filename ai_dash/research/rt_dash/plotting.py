from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats


def _aggregate_with_ci(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for (policy, load), subset in frame.groupby(["policy", "target_utilization"]):
        values = subset[metric].dropna().astype(float)
        n = len(values)
        mean = values.mean()
        sd = values.std(ddof=1) if n > 1 else 0.0
        half = stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n) if n > 1 else 0.0
        rows.append(
            {
                "policy": policy,
                "target_utilization": load,
                "mean": mean,
                "ci95": half,
            }
        )
    return pd.DataFrame(rows)


def plot_controlled(summary_csv: Path, output_dir: Path) -> None:
    frame = pd.read_csv(summary_csv)
    output_dir.mkdir(parents=True, exist_ok=True)

    specifications = [
        ("high_deadline_miss_ratio", "High-criticality deadline-miss ratio", "high_criticality_dmr.png"),
        ("high_mean_response", "Mean high-criticality response time (ms)", "high_criticality_response.png"),
        ("low_completion_rate", "Low-criticality completion rate", "low_criticality_completion.png"),
        ("mode_transitions", "Number of mode transitions", "mode_transitions.png"),
    ]
    combined: list[pd.DataFrame] = []
    for metric, ylabel, filename in specifications:
        grouped = _aggregate_with_ci(frame, metric)
        grouped["metric"] = metric
        combined.append(grouped)
        plt.figure(figsize=(8, 5))
        for policy, group in grouped.groupby("policy"):
            group = group.sort_values("target_utilization")
            plt.errorbar(
                group["target_utilization"],
                group["mean"],
                yerr=group["ci95"],
                marker="o",
                capsize=3,
                label=policy,
            )
        plt.xlabel("Target nominal utilization")
        plt.ylabel(ylabel)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / filename, dpi=600)
        plt.close()

    pd.concat(combined, ignore_index=True).to_csv(
        output_dir / "controlled_aggregates.csv", index=False
    )
