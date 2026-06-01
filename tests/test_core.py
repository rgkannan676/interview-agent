"""Unit tests for core components."""

import json
import pytest
from unittest.mock import patch, MagicMock

from config import DIMENSION_WEIGHTS, DIMENSIONS, QUESTIONS_PER_TYPE


# ---------- Config sanity ----------

def test_dimension_weights_sum_to_one():
    for interview_type, weights in DIMENSION_WEIGHTS.items():
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-6, f"{interview_type} weights sum to {total}"


def test_all_dimensions_covered():
    for interview_type, weights in DIMENSION_WEIGHTS.items():
        assert set(weights.keys()) == set(DIMENSIONS), \
            f"{interview_type} is missing some dimensions"


def test_questions_per_type_positive():
    for t, n in QUESTIONS_PER_TYPE.items():
        assert n > 0, f"{t} has {n} questions"


# ---------- Speech metrics ----------

def test_filler_rate_calculation():
    from config import FILLER_WORDS
    words = ["um", "I", "think", "like", "this", "uh", "works"]
    filler_count = sum(1 for w in words if w.lower() in FILLER_WORDS)
    rate = filler_count / len(words)
    assert filler_count == 3
    assert abs(rate - 3 / 7) < 1e-6


def test_letter_grade_boundaries():
    from agents.evaluator_agent import _letter_grade
    assert _letter_grade(9.5) == "A+"
    assert _letter_grade(8.0) == "A"
    assert _letter_grade(7.0) == "B"
    assert _letter_grade(6.0) == "C"
    assert _letter_grade(5.0) == "D"
    assert _letter_grade(4.9) == "F"


# ---------- Evaluator weighted score ----------

def test_weighted_score_within_range():
    from agents.evaluator_agent import _letter_grade
    weights = DIMENSION_WEIGHTS["Technical"]
    raw_scores = {dim: 7 for dim in DIMENSIONS}
    overall = sum(raw_scores[dim] * weights[dim] for dim in DIMENSIONS)
    assert 0 <= overall <= 10


# ---------- Session state ----------

def test_start_session_initialises_correctly():
    from agents.interviewer_agent import start_session
    state = start_session("SWE", "Technical", "Mid")
    assert state["role"] == "SWE"
    assert state["interview_type"] == "Technical"
    assert state["difficulty"] == "Mid"
    assert state["history"] == []
    assert state["max_questions"] == QUESTIONS_PER_TYPE["Technical"]
    assert state["done"] is False
