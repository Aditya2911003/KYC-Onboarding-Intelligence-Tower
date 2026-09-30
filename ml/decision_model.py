"""Two honest ML experiments on the KYC decision labels (section 6.7).

The labelled decisions come from a deterministic rule engine, so a model can
only re-learn the rules. The experiments make that explicit:

(a) all features, including PEP, sanction and risk tier: the model re-learns the
    policy; the residual error is the EDD-versus-Manual-Review split for High-risk
    non-PEP cases, which no field explains.
(b) without PEP, sanction and risk tier: the model barely beats the majority-class
    baseline, showing there is no hidden signal in the remaining columns.

Results (metrics, confusion, permutation and SHAP importance) are written to
``mart_ml_results.parquet`` in long format and shown on the "Model and method"
page as: "a model cannot beat the policy, and here is the proof".

Usage::

    python ml/decision_model.py --db data/warehouse.duckdb --out-dir data/marts
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.quality_checks import record_mart_check  # noqa: E402
from ml.explain import permutation_importance_frame, shap_importance_frame  # noqa: E402

LOG = logging.getLogger("decision_model")
SEED = 42
TEST_SIZE = 0.2
SHAP_SAMPLE = 2_000

POLICY_FEATURES = ("is_pep", "is_sanctioned", "risk_category")
CATEGORICAL = ("risk_category", "country", "occupation", "account_type", "gender")
ALL_FEATURES = (
    "is_sanctioned",
    "is_pep",
    "risk_category",
    "verified_docs",
    "aml_flag",
    "identity_verified",
    "address_verified",
    "country",
    "occupation",
    "account_type",
    "gender",
    "income",
    "age",
)
EXPERIMENTS = {
    "A_all_features": ALL_FEATURES,
    "B_without_pep_sanction_risk": tuple(f for f in ALL_FEATURES if f not in POLICY_FEATURES),
}


def load_features(db_path: Path) -> pd.DataFrame:
    """Load one row per case with the candidate features and the label."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.execute(
            """
            SELECT f.case_id, f.decision, f.is_sanctioned, f.is_pep, f.risk_category,
                   f.verified_docs, f.aml_flag, f.identity_verified, f.address_verified,
                   f.country, f.occupation, f.account_type, c.gender, f.income, c.age
            FROM fact_case AS f
            JOIN dim_customer AS c USING (customer_id)
            ORDER BY f.case_id
            """
        ).df()
    finally:
        con.close()


def encode(frame: pd.DataFrame, features: tuple[str, ...]) -> pd.DataFrame:
    """Encode booleans as 0/1 and categoricals as stable integer codes."""
    out = pd.DataFrame(index=frame.index)
    for col in features:
        if col in CATEGORICAL:
            out[col] = pd.Categorical(frame[col], categories=sorted(frame[col].unique())).codes
        else:
            out[col] = frame[col].astype(float)
    return out


def run_experiment(frame: pd.DataFrame, name: str, features: tuple[str, ...]) -> list[dict]:
    """Fit, evaluate and explain one experiment; return long-format result rows."""
    x = encode(frame, features)
    y = frame["decision"]
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=TEST_SIZE, stratify=y, random_state=SEED)
    # Categoricals are passed as ordinal codes on numeric splits (not native
    # categorical splits) because SHAP's tree conversion does not support HGB
    # categorical bitsets; the trees can still isolate any single code.
    model = HistGradientBoostingClassifier(random_state=SEED)
    model.fit(x_train, y_train)
    pred = model.predict(x_test)

    majority = y_train.value_counts().idxmax()
    baseline = float((y_test == majority).mean())
    accuracy = float(accuracy_score(y_test, pred))
    rows: list[dict] = [
        {"experiment": name, "kind": "metric", "name": "accuracy", "value": accuracy, "std": None},
        {
            "experiment": name,
            "kind": "metric",
            "name": "macro_f1",
            "value": float(f1_score(y_test, pred, average="macro")),
            "std": None,
        },
        {"experiment": name, "kind": "metric", "name": "baseline_accuracy", "value": baseline, "std": None},
        {"experiment": name, "kind": "metric", "name": "lift_pp", "value": 100 * (accuracy - baseline), "std": None},
        {"experiment": name, "kind": "metric", "name": "n_train", "value": float(len(x_train)), "std": None},
        {"experiment": name, "kind": "metric", "name": "n_test", "value": float(len(x_test)), "std": None},
        {"experiment": name, "kind": "metric", "name": "n_features", "value": float(len(features)), "std": None},
    ]
    confusion = pd.crosstab(y_test, pred)
    for true_label in confusion.index:
        for pred_label in confusion.columns:
            rows.append(
                {
                    "experiment": name,
                    "kind": "confusion",
                    "name": f"{true_label} -> {pred_label}",
                    "value": float(confusion.loc[true_label, pred_label]),
                    "std": None,
                }
            )
    perm = permutation_importance_frame(model, x_test, y_test, seed=SEED)
    rows += [
        {
            "experiment": name,
            "kind": "permutation_importance",
            "name": r.feature,
            "value": float(r.importance),
            "std": float(r.std),
        }
        for r in perm.itertuples()
    ]
    shap_frame = shap_importance_frame(model, x_test.sample(min(SHAP_SAMPLE, len(x_test)), random_state=SEED))
    rows += [
        {"experiment": name, "kind": "shap_importance", "name": r.feature, "value": float(r.importance), "std": None}
        for r in shap_frame.itertuples()
    ]
    rows.append(
        {
            "experiment": name,
            "kind": "metric",
            "name": "shap_available",
            "value": float(not shap_frame.empty),
            "std": None,
        }
    )
    LOG.info("%s: accuracy %.4f vs majority baseline %.4f", name, accuracy, baseline)
    return rows


def run(db_path: Path, out_dir: Path) -> pd.DataFrame:
    """Run both experiments and write ``mart_ml_results.parquet``."""
    frame = load_features(db_path)
    rows: list[dict] = []
    for name, features in EXPERIMENTS.items():
        rows += run_experiment(frame, name, features)
    results = pd.DataFrame(rows)
    results["std"] = results["std"].astype(float)
    out_dir.mkdir(parents=True, exist_ok=True)
    results.to_parquet(out_dir / "mart_ml_results.parquet", compression="zstd", index=False)
    record_mart_check(out_dir, "mart_ml_results")
    LOG.info("wrote %s rows to %s", len(results), out_dir / "mart_ml_results.parquet")
    return results


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=Path("data/warehouse.duckdb"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/marts"))
    args = parser.parse_args(argv)
    run(args.db, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
