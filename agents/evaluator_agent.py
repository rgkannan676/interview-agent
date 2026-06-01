"""Evaluator Agent — per-answer scoring and final session report generation."""

import json
import os

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from config import GROQ_MODEL, DIMENSIONS, DIMENSION_WEIGHTS

_llm: ChatGroq | None = None


def _get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        _llm = ChatGroq(model=GROQ_MODEL, api_key=os.environ["GROQ_API_KEY"], temperature=0.2)
    return _llm

_SCORE_SYSTEM = """You are an expert interview coach. Score the candidate's answer across these dimensions (0–10 each):
- technical_accuracy: correctness of technical content
- communication_clarity: how clearly the idea is expressed
- star_compliance: use of Situation-Task-Action-Result structure
- depth_of_answer: thoroughness of topic coverage
- confidence_signal: confidence inferred from word choice and fluency
- conciseness: answer length vs ideal benchmark

Respond with ONLY valid JSON matching this schema:
{
  "technical_accuracy": <int 0-10>,
  "communication_clarity": <int 0-10>,
  "star_compliance": <int 0-10>,
  "depth_of_answer": <int 0-10>,
  "confidence_signal": <int 0-10>,
  "conciseness": <int 0-10>,
  "ideal_answer": "<brief ideal answer>",
  "feedback": "<one paragraph of coaching feedback>"
}"""


def score_answer(
    question: str,
    answer: str,
    interview_type: str,
    speech_metrics: dict,
) -> dict:
    """Score a single answer. Returns dimension scores + weighted overall + ideal answer."""
    prompt = (
        f"Interview Type: {interview_type}\n"
        f"Question: {question}\n"
        f"Candidate Answer: {answer}\n"
        f"Speech Metrics: WPM={speech_metrics.get('wpm')}, "
        f"Filler Rate={speech_metrics.get('filler_rate'):.1%}, "
        f"Word Count={speech_metrics.get('word_count')}"
    )
    response = _get_llm().invoke([SystemMessage(content=_SCORE_SYSTEM), HumanMessage(content=prompt)])
    scores = json.loads(response.content.strip())

    weights = DIMENSION_WEIGHTS[interview_type]
    overall = sum(scores[dim] * weights[dim] for dim in DIMENSIONS)
    scores["overall_score"] = round(overall, 2)
    scores["speech_metrics"] = speech_metrics
    return scores


def generate_session_report(
    role: str,
    interview_type: str,
    difficulty: str,
    history: list[dict],
) -> dict:
    """Aggregate per-answer scores into a final session report with recommendations."""
    per_question = [h["scores"] for h in history]
    avg_scores = {
        dim: round(sum(q[dim] for q in per_question) / len(per_question), 2)
        for dim in DIMENSIONS
    }
    overall_avg = round(sum(q["overall_score"] for q in per_question) / len(per_question), 2)

    avg_wpm = round(sum(q["speech_metrics"]["wpm"] for q in per_question) / len(per_question), 1)
    avg_filler = round(sum(q["speech_metrics"]["filler_rate"] for q in per_question) / len(per_question), 4)

    grade = _letter_grade(overall_avg)

    coaching_prompt = (
        f"Role: {role} | Type: {interview_type} | Difficulty: {difficulty}\n"
        f"Average Scores: {avg_scores}\n"
        f"Overall: {overall_avg}/10 | Grade: {grade}\n"
        "Give 3–5 specific, actionable coaching recommendations."
    )
    coaching_response = _get_llm().invoke([HumanMessage(content=coaching_prompt)])

    return {
        "role": role,
        "interview_type": interview_type,
        "difficulty": difficulty,
        "grade": grade,
        "overall_score": overall_avg,
        "dimension_averages": avg_scores,
        "avg_wpm": avg_wpm,
        "avg_filler_rate": avg_filler,
        "per_question_breakdown": [
            {"question": h["question"], "answer": h["answer"], "scores": h["scores"]}
            for h in history
        ],
        "coaching_recommendations": coaching_response.content.strip(),
    }


def _letter_grade(score: float) -> str:
    if score >= 9:
        return "A+"
    elif score >= 8:
        return "A"
    elif score >= 7:
        return "B"
    elif score >= 6:
        return "C"
    elif score >= 5:
        return "D"
    return "F"
