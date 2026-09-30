"""Model explanation helpers: permutation importance and (where supported) SHAP.

Permutation importance is model-agnostic and always computed. SHAP is attempted
with ``shap.TreeExplainer``; if the installed SHAP version cannot explain the
estimator, the function returns an empty frame and the caller records that
SHAP was skipped rather than faking values.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

LOG = logging.getLogger("explain")


def permutation_importance_frame(
    model: object, x_test: pd.DataFrame, y_test: pd.Series, seed: int = 42, n_repeats: int = 5
) -> pd.DataFrame:
    """Return mean and std accuracy drop per feature, sorted descending."""
    result = permutation_importance(
        model, x_test, y_test, n_repeats=n_repeats, random_state=seed, scoring="accuracy", n_jobs=1
    )
    frame = pd.DataFrame(
        {
            "feature": x_test.columns,
            "importance": result.importances_mean,
            "std": result.importances_std,
        }
    )
    return frame.sort_values("importance", ascending=False).reset_index(drop=True)


def _to_rows_features_classes(values: object, n_rows: int) -> np.ndarray:
    """Normalise SHAP output to shape (rows, features, classes)."""
    arr = np.stack(values, axis=-1) if isinstance(values, list) else np.asarray(values)
    if arr.ndim == 2:
        arr = arr[..., np.newaxis]
    if arr.shape[0] != n_rows:
        arr = np.moveaxis(arr, 0, -1)
    return arr


def shap_is_additive(model: object, explainer: object, arr: np.ndarray, x_sample: pd.DataFrame) -> bool:
    """Check SHAP's local-accuracy property: base value + sum(SHAP) == raw model output.

    If this fails, the SHAP values do not describe the model and must not be shown.
    """
    raw = np.asarray(model.decision_function(x_sample))  # type: ignore[attr-defined]
    if raw.ndim == 1:
        raw = raw[:, np.newaxis]
    base = np.atleast_1d(np.asarray(explainer.expected_value))  # type: ignore[attr-defined]
    reconstructed = arr.sum(axis=1) + base
    return reconstructed.shape == raw.shape and bool(np.allclose(reconstructed, raw, atol=1e-3))


def shap_importance_frame(model: object, x_sample: pd.DataFrame) -> pd.DataFrame:
    """Return mean |SHAP| per feature (averaged over classes), or an empty frame.

    SHAP is only reported when it is supported for the estimator and passes the
    additivity check; otherwise an empty frame is returned and the caller
    records that SHAP was skipped.

    Args:
        model: a fitted tree ensemble.
        x_sample: rows to explain (a few thousand is plenty).
    """
    empty = pd.DataFrame(columns=["feature", "importance", "std"])
    try:
        import shap  # dev-only dependency

        explainer = shap.TreeExplainer(model)
        values = explainer.shap_values(x_sample, check_additivity=False)
    except Exception as exc:  # SHAP support varies by estimator and version
        LOG.warning("SHAP skipped: %s", exc)
        return empty
    arr = _to_rows_features_classes(values, len(x_sample))
    if not shap_is_additive(model, explainer, arr, x_sample):
        LOG.warning("SHAP skipped: values fail the additivity check for this estimator")
        return empty
    per_feature = np.abs(arr).mean(axis=(0, 2))
    frame = pd.DataFrame({"feature": x_sample.columns, "importance": per_feature, "std": np.nan})
    return frame.sort_values("importance", ascending=False).reset_index(drop=True)
