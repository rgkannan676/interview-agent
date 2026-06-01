"""FastAPI backend — session management and job description upload."""

import datetime
import json
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import JD_UPLOADS_DIR, SESSIONS_DIR, INTERVIEW_TYPES, DIFFICULTY_LEVELS
from agents.interviewer_agent import start_session, generate_opening_question, generate_followup_question
from agents.evaluator_agent import score_answer, generate_session_report
from agents.speech import transcribe_audio, synthesize_speech
from rag.rag import ingest_job_description, retrieve_jd_context, index_question_bank
from mlops.tracker import log_session

app = FastAPI(title="InterviewIQ API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Index question bank at startup so retrieve_questions() works in the interviewer agent
try:
    index_question_bank()
except Exception:
    pass

# In-memory session store (replace with Redis for production)
_sessions: dict[str, dict] = {}


class SessionCreateRequest(BaseModel):
    role: str
    interview_type: str
    difficulty: str
    jd_text: str = ""
    num_questions: int = 0


class AnswerSubmitRequest(BaseModel):
    session_id: str
    transcript: str
    speech_metrics: dict


@app.post("/session/create")
async def create_session(req: SessionCreateRequest):
    if req.interview_type not in INTERVIEW_TYPES:
        raise HTTPException(400, f"interview_type must be one of {INTERVIEW_TYPES}")
    if req.difficulty not in DIFFICULTY_LEVELS:
        raise HTTPException(400, f"difficulty must be one of {DIFFICULTY_LEVELS}")

    session_id = str(uuid.uuid4())
    jd_context = ""
    if req.jd_text.strip():
        ingest_job_description(session_id, req.jd_text)
        jd_context = req.jd_text[:2000]  # seed context; RAG used per-question

    state = start_session(req.role, req.interview_type, req.difficulty, jd_context, req.num_questions)
    state = generate_opening_question(state)
    _sessions[session_id] = {"state": state, "session_id": session_id}

    return {
        "session_id": session_id,
        "first_question": state["current_question"],
        "max_questions": state["max_questions"],
    }


@app.post("/session/answer")
async def submit_answer(req: AnswerSubmitRequest):
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    state = session["state"]
    current_question = state["current_question"]

    scores = score_answer(
        question=current_question,
        answer=req.transcript,
        interview_type=state["interview_type"],
        speech_metrics=req.speech_metrics,
    )
    state["history"].append({
        "question": current_question,
        "answer": req.transcript,
        "scores": scores,
    })

    if len(state["history"]) >= state["max_questions"]:
        report = generate_session_report(
            state["role"], state["interview_type"], state["difficulty"], state["history"]
        )
        _persist_session(req.session_id, report)
        log_session(req.session_id, report)
        return {"done": True, "report": report}

    state = generate_followup_question(state)
    _sessions[req.session_id]["state"] = state
    return {"done": False, "next_question": state["current_question"], "scores": scores}


@app.post("/session/end")
async def end_session(req: dict):
    session_id = req.get("session_id")
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    state = session["state"]
    if not state["history"]:
        raise HTTPException(400, "No answers recorded yet — answer at least one question before ending.")
    report = generate_session_report(
        state["role"], state["interview_type"], state["difficulty"], state["history"]
    )
    _persist_session(session_id, report)
    log_session(session_id, report)
    del _sessions[session_id]
    return {"done": True, "report": report}


@app.post("/session/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Receive an audio file, transcribe via Groq Whisper, return transcript + speech metrics."""
    suffix = Path(file.filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = transcribe_audio(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return result


@app.post("/session/upload-jd")
async def upload_jd(file: UploadFile = File(...)):
    content = await file.read()
    dest = JD_UPLOADS_DIR / file.filename
    dest.write_bytes(content)
    return {"filename": file.filename, "size": len(content)}


@app.get("/sessions/list")
async def list_sessions():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    sessions = []
    for path in sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text())
            sessions.append({
                "session_id": data.get("session_id", path.stem),
                "role": data.get("role", "Unknown"),
                "interview_type": data.get("interview_type", ""),
                "difficulty": data.get("difficulty", ""),
                "grade": data.get("grade", "?"),
                "overall_score": data.get("overall_score", 0),
                "question_count": len(data.get("per_question_breakdown", [])),
                "created_at": data.get("created_at", ""),
            })
        except Exception:
            continue
    return {"sessions": sessions}


@app.get("/session/{session_id}/report")
async def get_report(session_id: str):
    report_path = SESSIONS_DIR / f"{session_id}.json"
    if not report_path.exists():
        raise HTTPException(404, "Report not found")
    return json.loads(report_path.read_text())


@app.delete("/session/{session_id}")
async def delete_session_report(session_id: str):
    report_path = SESSIONS_DIR / f"{session_id}.json"
    if not report_path.exists():
        raise HTTPException(404, "Session not found")
    report_path.unlink()
    _sessions.pop(session_id, None)
    return {"deleted": session_id}


def _persist_session(session_id: str, report: dict):
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    report["session_id"] = session_id
    report["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    path = SESSIONS_DIR / f"{session_id}.json"
    path.write_text(json.dumps(report, indent=2))
