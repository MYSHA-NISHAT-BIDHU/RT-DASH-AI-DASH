from rt_dash.imc import (
    MCBenchmarkConfig,
    MCPolicy,
    generate_mc_taskset,
    run_mc_benchmark,
    summarize_mc,
    virtual_deadline_factor,
)


def test_generated_taskset_has_valid_virtual_deadline_factor():
    tasks = generate_mc_taskset(12, 0.75, 0.3, 1.5, 0.5, 1)
    assert 0 < virtual_deadline_factor(tasks) < 1


def test_imc_benchmark_executes_all_policies():
    tasks = generate_mc_taskset(10, 0.65, 0.3, 1.5, 0.5, 3)
    for policy in MCPolicy:
        result = run_mc_benchmark(
            tasks,
            MCBenchmarkConfig(duration=2000, policy=policy, seed=7),
        )
        summary = summarize_mc(result)
        assert summary["policy"] == policy.value
        assert 0 <= summary["processor_utilization"] <= 1
