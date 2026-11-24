import numpy as np
import pytest

from rt_dash.ai import (
    PortableLogisticRiskModel,
    choose_safety_threshold,
    cluster_bootstrap_mean_ci,
    expected_calibration_error,
    predictive_signals,
    sensor_outage_feature_matrix,
)


def test_portable_logistic_model_is_numerically_stable():
    model = PortableLogisticRiskModel(
        feature_names=("a", "b"),
        mean=np.array([0.0, 1.0]),
        scale=np.array([1.0, 2.0]),
        coefficients=np.array([1000.0, -1000.0]),
        intercept=0.0,
    )
    values = model.predict_proba(np.array([[1000.0, -1000.0], [-1000.0, 1000.0]]))
    assert np.isfinite(values).all()
    assert values[0] > 0.999
    assert values[1] < 0.001


def test_safety_threshold_is_deterministic():
    labels = np.array([0, 0, 1, 1], dtype=np.uint8)
    probabilities = np.array([0.1, 0.4, 0.6, 0.9])
    first = choose_safety_threshold(labels, probabilities, 5.0, 1.0)
    second = choose_safety_threshold(labels, probabilities, 5.0, 1.0)
    assert first == second
    assert 0.0 <= first[0] <= 1.0


def test_sensor_outage_zeroes_only_matching_channels():
    names = (
        "sensor_current__door",
        "sensor_current__light",
        "sensor_mean_60s__door",
        "time_of_day_sin",
    )
    data = np.ones((2, 4), dtype=np.float32)
    result = sensor_outage_feature_matrix(data, names, ["door"])
    assert np.all(result[:, [0, 2]] == 0)
    assert np.all(result[:, [1, 3]] == 1)
    assert np.all(data == 1)


def test_predictive_signal_schedule_is_causal_and_aligned():
    signals = predictive_signals([0.1, 0.8], step_ms=100, start_ms=20)
    assert [signal.time for signal in signals] == [20, 120]
    assert all(signal.generated_at == signal.time for signal in signals)


def test_portable_model_round_trip_preserves_probabilities(tmp_path):
    model = PortableLogisticRiskModel(
        feature_names=("door", "light"),
        mean=np.array([0.2, 0.8]),
        scale=np.array([0.4, 0.5]),
        coefficients=np.array([1.25, -0.75]),
        intercept=0.1,
    )
    path = tmp_path / "model.json"
    model.save(path)
    restored = PortableLogisticRiskModel.load(path)
    features = np.array([[0.0, 1.0], [1.0, 0.0]])
    assert np.allclose(model.predict_proba(features), restored.predict_proba(features))


def test_portable_model_rejects_wrong_feature_width():
    model = PortableLogisticRiskModel(
        feature_names=("a", "b"),
        mean=np.zeros(2),
        scale=np.ones(2),
        coefficients=np.ones(2),
        intercept=0.0,
    )
    with pytest.raises(ValueError, match="feature matrix width"):
        model.predict_proba(np.ones((1, 3)))


def test_perfect_probabilities_have_zero_calibration_error():
    labels = np.array([0, 0, 1, 1], dtype=np.uint8)
    probabilities = labels.astype(float)
    assert expected_calibration_error(labels, probabilities, bins=5) == 0.0


def test_cluster_bootstrap_interval_is_reproducible():
    values = np.array([1.0, 2.0, 4.0, 8.0])
    clusters = np.array([0, 0, 1, 1])
    first = cluster_bootstrap_mean_ci(values, clusters, seed=123, resamples=1000)
    second = cluster_bootstrap_mean_ci(values, clusters, seed=123, resamples=1000)
    assert first == second
    assert first[0] <= values.mean() <= first[1]


def test_safety_threshold_rejects_empty_inputs():
    with pytest.raises(ValueError, match="equally non-empty"):
        choose_safety_threshold(np.array([], dtype=np.uint8), np.array([]))
