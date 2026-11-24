import numpy as np

from rt_dash.forecasting import (
    ARIMA510,
    NumpyLSTMRegressor,
    ForecastExamples,
    RidgeVARRegressor,
    convex_blend_predictions,
    exponentially_weighted_history_prediction,
    select_convex_blend_weights,
    thesis_hybrid_pressure,
)


def test_arima_510_forecasts_linear_first_difference() -> None:
    values = np.arange(80, dtype=float)
    model = ARIMA510().fit(values)
    prediction = model.forecast(values[-12:], steps=1)[0]
    assert np.isclose(prediction, 80.0, atol=1e-8)


def test_numpy_lstm_learns_simple_multivariate_next_step_mapping() -> None:
    rng = np.random.default_rng(17)
    x = rng.normal(size=(160, 5, 4))
    y = 0.8 * x[:, -1, :] + 0.2 * x[:, -2, :]
    model = NumpyLSTMRegressor(hidden_size=10, seed=9)
    before = float(np.mean((model.predict(x[120:]) - y[120:]) ** 2))
    history = model.fit(
        x[:120], y[:120], x[120:], y[120:],
        learning_rate=0.01, batch_size=32, max_epochs=20, patience=5,
    )
    after = float(np.mean((model.predict(x[120:]) - y[120:]) ** 2))
    assert history
    assert np.isfinite(after)
    assert after < before


def test_numpy_lstm_bptt_gradient_matches_finite_difference() -> None:
    rng = np.random.default_rng(4)
    x = rng.normal(size=(2, 3, 2))
    y = rng.normal(size=(2, 1))
    model = NumpyLSTMRegressor(input_size=2, hidden_size=2, output_size=1, seed=3)
    _, gradients = model._loss_and_gradients(x, y)
    epsilon = 1e-5
    coordinates = (
        ("Wx", (0, 0)),
        ("Wh", (0, 1)),
        ("b", (0,)),
        ("Wy", (0, 0)),
        ("by", (0,)),
    )
    for name, index in coordinates:
        parameter = model.parameters[name]
        original = float(parameter[index])
        parameter[index] = original + epsilon
        plus = float(np.mean((model.predict(x) - y) ** 2))
        parameter[index] = original - epsilon
        minus = float(np.mean((model.predict(x) - y) ** 2))
        parameter[index] = original
        numerical = (plus - minus) / (2.0 * epsilon)
        assert np.isclose(gradients[name][index], numerical, rtol=2e-4, atol=2e-5)


def test_thesis_hybrid_pressure_is_bounded_and_monotone_for_high_resources() -> None:
    train = np.column_stack([np.arange(100, dtype=float)] * 4)
    low = thesis_hybrid_pressure(np.array([[10.0, 10.0, 10.0, 10.0]]), train)[0]
    high = thesis_hybrid_pressure(np.array([[90.0, 90.0, 90.0, 90.0]]), train)[0]
    assert 0.0 <= low < high <= 1.0


def test_exponential_history_forecast_is_causal_and_resource_specific() -> None:
    x = np.array([[[0.0, 10.0], [10.0, 20.0], [20.0, 30.0]]])
    examples = ForecastExamples(
        x=x,
        y=np.array([[999.0, 999.0]]),
        target_indices=np.array([3]),
        splits=np.array(["validation"]),
    )
    prediction = exponentially_weighted_history_prediction(examples, np.array([1.0, 0.5]))
    assert np.allclose(prediction[0], [20.0, 22.5])


def test_ridge_var_learns_linear_multivariate_mapping() -> None:
    rng = np.random.default_rng(11)
    x = rng.normal(size=(200, 3, 2))
    y = np.column_stack(
        [0.7 * x[:, -1, 0] - 0.2 * x[:, -2, 1], x[:, -1, 1] + 0.1]
    )
    model = RidgeVARRegressor(ridge=1e-6).fit(x[:160], y[:160])
    prediction = model.predict(x[160:])
    assert np.mean((prediction - y[160:]) ** 2) < 1e-10


def test_convex_blend_selects_validation_optimum_without_target_leakage() -> None:
    actual = np.array([[0.0, 0.0], [2.0, 2.0]])
    arima = np.array([[0.0, 2.0], [2.0, 4.0]])
    lstm = np.array([[2.0, 0.0], [4.0, 2.0]])
    weights = select_convex_blend_weights(actual, arima, lstm, np.array([0.0, 1.0]))
    assert np.allclose(weights, [0.0, 1.0])
    blended = convex_blend_predictions(arima, lstm, weights)
    assert np.allclose(blended, actual)
