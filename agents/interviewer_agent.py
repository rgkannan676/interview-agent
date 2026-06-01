"""Interviewer Agent — generates opening questions and follow-ups via Groq LLM."""

import os
from typing import Any

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from config import GROQ_MODEL, QUESTIONS_PER_TYPE

_llm: ChatGroq | None = None


def _get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        _llm = ChatGroq(model=GROQ_MODEL, api_key=os.environ["GROQ_API_KEY"], temperature=0.7)
    return _llm


# ---------- State ----------

class InterviewState(dict):
    """Typed LangGraph state for an interview session."""
    role: str
    interview_type: str
    difficulty: str
    jd_context: str
    history: list[dict]        # [{question, answer, scores}]
    current_question: str
    question_count: int
    max_questions: int
    done: bool


# ---------- Role → hint mapping ----------

# ---------- Prompts ----------

_INTERVIEW_TYPE_GUIDANCE = {
    "Technical": (
        "Ask questions about technical depth: algorithms, data structures, system internals, "
        "language features, debugging, and implementation trade-offs. "
        "Do NOT ask behavioural or system design questions."
    ),
    "Behavioural": (
        "Ask STAR-format questions (Situation, Task, Action, Result) about the candidate's "
        "past experiences — teamwork, conflict, failure, leadership, prioritisation. "
        "Probe for specific real examples, never hypotheticals. "
        "Do NOT ask technical coding or system design questions."
    ),
    "System Design": (
        "Ask the candidate to design a scalable, real-world system. Probe for scalability, "
        "availability, consistency trade-offs, data modelling, API design, and architectural "
        "decisions. Do NOT ask pure algorithm or behavioural questions."
    ),
}

_DIFFICULTY_GUIDANCE = {
    "Junior":    "Keep questions at a foundational level — core concepts and basic implementations.",
    "Mid":       "Expect working production experience and trade-off discussions.",
    "Senior":    "Expect deep expertise, architectural thinking, and examples of engineering leadership.",
    "Principal": "Expect organisation-wide impact, long-term system strategy, and cross-team influence.",
}


def _system_prompt(state: InterviewState) -> str:
    type_guide = _INTERVIEW_TYPE_GUIDANCE.get(state["interview_type"], "")
    diff_guide = _DIFFICULTY_GUIDANCE.get(state["difficulty"], "")
    return (
        f"You are an expert interviewer hiring for a {state['role']} position.\n"
        f"This is a {state['difficulty']}-level {state['interview_type']} interview.\n\n"
        f"Interview type: {type_guide}\n"
        f"Difficulty expectation: {diff_guide}\n\n"
        "Rules:\n"
        "- Output ONLY the question — no preamble, no labels, no commentary.\n"
        "- Ask exactly one focused question at a time.\n"
        "- Never repeat a previous question.\n"
        "- Adapt each question to the candidate's prior answers and job context.\n"
        f"\nJob Context:\n{state['jd_context'] or 'Not provided.'}"
    )


def _seed_questions(state: InterviewState, topic_hint: str = "") -> str:
    """Pull question-bank examples relevant to the role, type, difficulty, and JD."""
    try:
        from rag.rag import retrieve_questions
        jd_snippet = (state.get("jd_context") or "")[:200]
        query_parts = [state["role"], state["interview_type"], state["difficulty"]]
        if topic_hint:
            query_parts.append(topic_hint)
        if jd_snippet:
            query_parts.append(jd_snippet)
        query = " ".join(query_parts)

        questions = retrieve_questions(
            query=query,
            interview_type=state["interview_type"],
            difficulty=state["difficulty"],
            n_results=3,
        )
    except Exception:
        questions = []
    if not questions:
        return ""
    lines = "\n".join(f"  - {q}" for q in questions)
    return (
        f"\n\nQuestion bank examples for reference — use them for style/level inspiration "
        f"ONLY if they are relevant to the {state['role']} role. "
        f"If they don't match the role, ignore them and generate your own question "
        f"that fits the role and level precisely:\n{lines}"
    )


# ---------- Nodes ----------

def generate_opening_question(state: InterviewState) -> InterviewState:
    seed = _seed_questions(state)
    messages = [
        SystemMessage(content=_system_prompt(state) + seed),
        HumanMessage(content="Ask your first interview question."),
    ]
    response = _get_llm().invoke(messages)
    state["current_question"] = response.content.strip()
    state["question_count"] = 1
    return state


def generate_followup_question(state: InterviewState) -> InterviewState:
    history = state["history"]
    history_text = "\n\n".join(
        f"Q{i+1}: {h['question']}\nA: {h['answer']}"
        for i, h in enumerate(history)
    )
    remaining = state["max_questions"] - len(history)

    # Last 2 questions — used to enforce the consecutive follow-up rule
    last_two = "\n".join(f"  - {h['question']}" for h in history[-2:])

    # Seed: use the last answer as topic hint so examples are contextually relevant
    last_answer = history[-1]["answer"] if history else ""
    seed = _seed_questions(state, topic_hint=last_answer[:200])

    messages = [
        SystemMessage(content=_system_prompt(state) + seed),
        HumanMessage(
            content=(
                f"Full interview history:\n{history_text}\n\n"
                f"Last 2 questions asked:\n{last_two}\n\n"
                f"Questions remaining in this session: {remaining}\n\n"
                "Decide your next question using these rules:\n"
                "1. You MAY ask one follow-up on the current topic IF the candidate's last answer "
                "was unclear, incomplete, or genuinely warrants probing deeper.\n"
                "2. If the last 2 questions were already on the same topic, you MUST move to a "
                "different area — do not ask a third consecutive question on the same subject.\n"
                "3. Aim to cover a broad range of areas across the role by the end of the session.\n"
                "4. Never repeat a question already asked."
            )
        ),
    ]
    response = _get_llm().invoke(messages)
    state["current_question"] = response.content.strip()
    state["question_count"] = len(history) + 1
    return state


def check_done(state: InterviewState) -> str:
    if len(state["history"]) >= state["max_questions"]:
        state["done"] = True
        return "done"
    return "continue"


# ---------- Graph ----------

def build_interviewer_graph() -> Any:
    graph = StateGraph(InterviewState)
    graph.add_node("opening", generate_opening_question)
    graph.add_node("followup", generate_followup_question)
    graph.add_conditional_edges("followup", check_done, {"done": END, "continue": "followup"})
    graph.set_entry_point("opening")
    graph.add_edge("opening", "followup")
    return graph.compile()


def start_session(role: str, interview_type: str, difficulty: str, jd_context: str = "", num_questions: int = 0) -> InterviewState:
    return InterviewState(
        role=role,
        interview_type=interview_type,
        difficulty=difficulty,
        jd_context=jd_context,
        history=[],
        current_question="",
        question_count=0,
        max_questions=num_questions if num_questions > 0 else QUESTIONS_PER_TYPE[interview_type],
        done=False,
    )
