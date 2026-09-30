"""AI-copilot answer-quality marts (section 6.6).

Reads ``benchmark_dataset.csv`` (faithful + hallucinated answers) and
``hallucinated_answers.csv`` (type and severity per hallucination) and builds:

* ``mart_ai_by_type``            answers, hallucinated, rate and length difference per type
* ``mart_ai_by_question``        hallucination % per masked question template
* ``mart_ai_severity``           hallucination type x severity
* ``mart_ai_detector_confusion`` confusion matrix of the rule-based detector
* ``mart_ai_detector_metrics``   precision / recall / F1 per type
* ``ai_examples.parquet``        at most 25 curated, ID-masked example answers

Customer IDs are masked with ``regexp_replace(text, 'C[0-9]+', 'C#', 'g')``. Once masked,
the answers collapse to 25 templates, so any detector scores near 100% by
construction; the app states this prominently. Raw answer text is never exported.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

NONE_TYPE = "NONE"
TYPES = (
    NONE_TYPE,
    "Contradiction",
    "Fabricated Regulation",
    "Missing Evidence",
    "Unsupported Claim",
    "Wrong Risk Score",
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_REGULATION_RE = re.compile(r"\b(regulation|section|article|act)\b\s*[\w.]*", re.IGNORECASE)
_RISK_RE = re.compile(r"\b(low|medium|high)\b[\w\s]*\brisk\b", re.IGNORECASE)


def split_sentences(text: str) -> list[str]:
    """Split an answer into trimmed sentences."""
    return [s.strip() for s in _SENTENCE_RE.split(text.strip()) if s.strip()]


def answer_outcome(text: str) -> str | None:
    """Map an answer to the onboarding outcome it asserts, or None if it hedges.

    Checked in order so that negations ("no enhanced review") win over the
    phrases they contain.
    """
    t = text.lower()
    if "rejected" in t:
        return "reject"
    if "no enhanced review" in t:
        return "approve"
    if "approved" in t:
        return "approve"
    if "insufficient" in t or "additional documents" in t:
        return "hold"
    if "enhanced due diligence" in t or "manual review" in t or "escalated" in t:
        return "escalate"
    return None


def detect(ground_truth: str, generated: str) -> tuple[str, str]:
    """Classify a generated answer against its ground truth.

    Transparent, reference-based rules (no training):

    1. identical text -> ``NONE`` (faithful)
    2. ground truth kept and a sentence appended -> the appended claim is typed:
       a cited regulation -> Fabricated Regulation; a risk level -> Wrong Risk
       Score; anything else -> Unsupported Claim
    3. ground truth replaced -> Contradiction if the new answer asserts a
       different definite outcome, else Missing Evidence (a hedge with no reason)

    Returns:
        (predicted type, flagged claim text)
    """
    if generated.strip() == ground_truth.strip():
        return NONE_TYPE, ""
    gt_sentences = split_sentences(ground_truth)
    gen_sentences = split_sentences(generated)
    extra = [s for s in gen_sentences if s not in gt_sentences]
    missing = [s for s in gt_sentences if s not in gen_sentences]
    claim = " ".join(extra) if extra else generated
    if extra and not missing:
        if _REGULATION_RE.search(claim):
            return "Fabricated Regulation", claim
        if _RISK_RE.search(claim):
            return "Wrong Risk Score", claim
        return "Unsupported Claim", claim
    gen_outcome = answer_outcome(generated)
    if gen_outcome is not None and gen_outcome != answer_outcome(ground_truth):
        return "Contradiction", claim
    return "Missing Evidence", claim


def detector_metrics(confusion: pd.DataFrame) -> pd.DataFrame:
    """Compute precision, recall and F1 per type from a long confusion table.

    Args:
        confusion: columns ``true_type``, ``predicted_type``, ``answers``.
    """
    rows = []
    for label in TYPES:
        tp = confusion.loc[(confusion.true_type == label) & (confusion.predicted_type == label), "answers"].sum()
        predicted = confusion.loc[confusion.predicted_type == label, "answers"].sum()
        actual = confusion.loc[confusion.true_type == label, "answers"].sum()
        precision = tp / predicted if predicted else 0.0
        recall = tp / actual if actual else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        rows.append(
            {
                "hallucination_type": label,
                "support": int(actual),
                "predicted": int(predicted),
                "true_positive": int(tp),
                "precision": round(float(precision), 4),
                "recall": round(float(recall), 4),
                "f1": round(float(f1), 4),
            }
        )
    return pd.DataFrame(rows)


def build_ai_marts(con: duckdb.DuckDBPyConnection, raw_dir: Path, out_dir: Path) -> None:
    """Create the AI marts as ``mart_ai_*`` tables and write ``ai_examples.parquet``."""
    raw = raw_dir.resolve().as_posix().replace("'", "''")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE stg_benchmark AS
        SELECT
            BenchmarkID                        AS benchmark_id,
            AnswerID                           AS answer_id,
            CustomerID                         AS customer_id,
            regexp_replace(Question, 'C[0-9]+', 'C#', 'g')          AS question_template,
            regexp_replace(GroundTruthAnswer, 'C[0-9]+', 'C#', 'g') AS ground_truth_masked,
            regexp_replace(GeneratedAnswer, 'C[0-9]+', 'C#', 'g')   AS generated_masked,
            length(GeneratedAnswer) - length(GroundTruthAnswer)     AS len_diff_chars,
            HallucinationType                  AS hallucination_type,
            CAST(Hallucinated AS INTEGER) = 1  AS is_hallucinated,
            CAST(ExpectedLabel AS INTEGER)     AS expected_label
        FROM read_csv('{raw}/benchmark_dataset.csv', header = true, auto_detect = true)
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE stg_hallucinated AS
        SELECT
            HallucinationID          AS hallucination_id,
            AnswerID                 AS answer_id,
            HallucinationType        AS hallucination_type,
            Severity                 AS severity,
            CAST(Hallucinated AS BOOLEAN) AS is_hallucinated
        FROM read_csv('{raw}/hallucinated_answers.csv', header = true, auto_detect = true)
        """
    )

    # Hallucination rate per type (the NONE type is the faithful control group).
    con.execute(
        """
        CREATE OR REPLACE TABLE mart_ai_by_type AS
        SELECT
            hallucination_type,
            COUNT(*)                                       AS answers,
            COUNT(*) FILTER (WHERE is_hallucinated)        AS hallucinated,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_hallucinated) / COUNT(*), 2) AS hallucination_rate_pct,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)                   AS share_of_answers_pct,
            ROUND(AVG(len_diff_chars), 2)                  AS avg_len_diff_chars
        FROM stg_benchmark
        GROUP BY hallucination_type
        """
    )
    # Hallucination % per masked question template (expected to be flat).
    con.execute(
        """
        CREATE OR REPLACE TABLE mart_ai_by_question AS
        SELECT
            question_template,
            COUNT(*)                                 AS answers,
            COUNT(*) FILTER (WHERE is_hallucinated)  AS hallucinated,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_hallucinated) / COUNT(*), 2) AS hallucination_pct
        FROM stg_benchmark
        GROUP BY question_template
        """
    )
    # Severity only exists for hallucinated answers, so this is a distribution.
    con.execute(
        """
        CREATE OR REPLACE TABLE mart_ai_severity AS
        SELECT
            hallucination_type,
            severity,
            COUNT(*) AS answers,
            ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY hallucination_type), 2) AS pct_of_type
        FROM stg_hallucinated
        GROUP BY hallucination_type, severity
        """
    )

    # Run the detector once per distinct masked (ground truth, generated) pair.
    pairs = con.execute(
        """
        SELECT ground_truth_masked, generated_masked, hallucination_type, COUNT(*) AS answers
        FROM stg_benchmark
        GROUP BY ALL
        """
    ).df()
    predictions = [detect(gt, gen) for gt, gen in zip(pairs.ground_truth_masked, pairs.generated_masked, strict=True)]
    pairs["predicted_type"] = [p[0] for p in predictions]
    pairs["flagged_claim"] = [p[1] for p in predictions]
    confusion = (
        pairs.groupby(["hallucination_type", "predicted_type"], as_index=False)["answers"]
        .sum()
        .rename(columns={"hallucination_type": "true_type"})
    )
    metrics = detector_metrics(confusion)
    con.register("confusion_df", confusion)
    con.execute("CREATE OR REPLACE TABLE mart_ai_detector_confusion AS SELECT * FROM confusion_df")
    con.unregister("confusion_df")
    con.register("metrics_df", metrics)
    con.execute("CREATE OR REPLACE TABLE mart_ai_detector_metrics AS SELECT * FROM metrics_df")
    con.unregister("metrics_df")

    # One curated example per masked generated-answer template (25 in the full data).
    con.register("pairs_df", pairs[["ground_truth_masked", "generated_masked", "predicted_type", "flagged_claim"]])
    out_dir.mkdir(parents=True, exist_ok=True)
    target = (out_dir / "ai_examples.parquet").as_posix().replace("'", "''")
    con.execute(
        f"""
        COPY (
            WITH ranked AS (
                SELECT
                    b.*,
                    h.severity,
                    COUNT(*) OVER (PARTITION BY b.generated_masked) AS answers_with_template,
                    ROW_NUMBER() OVER (PARTITION BY b.generated_masked ORDER BY b.benchmark_id) AS rn
                FROM stg_benchmark AS b
                LEFT JOIN stg_hallucinated AS h
                    ON h.answer_id = b.answer_id AND b.is_hallucinated
            )
            SELECT
                ROW_NUMBER() OVER (ORDER BY r.hallucination_type, r.generated_masked) AS example_id,
                r.question_template,
                r.hallucination_type,
                COALESCE(r.severity, 'n/a')   AS severity,
                r.ground_truth_masked,
                r.generated_masked,
                p.predicted_type              AS detector_prediction,
                p.flagged_claim,
                r.answers_with_template
            FROM ranked AS r
            JOIN pairs_df AS p
              ON p.ground_truth_masked = r.ground_truth_masked
             AND p.generated_masked = r.generated_masked
            WHERE r.rn = 1
            ORDER BY example_id
            LIMIT 25
        ) TO '{target}' (FORMAT parquet, COMPRESSION zstd)
        """
    )
    con.unregister("pairs_df")
