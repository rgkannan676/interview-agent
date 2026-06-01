"""MLflow session tracker — logs scores, speech metrics, and grades per interview session."""

import mlflow

from config import MLFLOW_TRACKING_URI, DIMENSIONS


def log_session(session_id: str, report: dict):
    """Log a completed interview session to MLflow."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("interviewiq")

    with mlflow.start_run(run_name=session_id):
        # Params
        mlflow.log_params({
            "role": report["role"],
            "interview_type": report["interview_type"],
            "difficulty": report["difficulty"],
        })

        # Summary metrics
        mlflow.log_metrics({
            "overall_score": report["overall_score"],
            "avg_wpm": report["avg_wpm"],
            "avg_filler_rate": report["avg_filler_rate"],
        })

        # Dimension averages
        for dim in DIMENSIONS:
            mlflow.log_metric(f"avg_{dim}", report["dimension_averages"].get(dim, 0))

        # Per-question metrics
        for i, qa in enumerate(report["per_question_breakdown"]):
            scores = qa["scores"]
            mlflow.log_metric(f"q{i+1}_overall", scores.get("overall_score", 0))
            mlflow.log_metric(f"q{i+1}_wpm", scores.get("speech_metrics", {}).get("wpm", 0))

        # Grade tag
        mlflow.set_tag("grade", report["grade"])
        mlflow.set_tag("session_id", session_id)
