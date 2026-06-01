"""Gradio UI — page routing and event handlers only."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gradio as gr
import httpx

from config import INTERVIEW_TYPES, DIFFICULTY_LEVELS, API_PORT, GRADIO_PORT, QUESTIONS_PER_TYPE
from agents.speech import synthesize_speech
from ui.templates import progress_html, question_html, score_html, report_html, warning_html, history_html, no_answers_html

API_BASE = f"http://localhost:{API_PORT}"
CSS = (Path(__file__).parent / "styles.css").read_text()

_session_id: str | None = None
_current_question: str = ""
_question_num: int = 0
_max_questions: int = 0


# ── Helpers ───────────────────────────────────────────────────────────────────

_DATE_FILTER_DAYS = {"Last 7 days": 7, "Last 30 days": 30, "Last 3 months": 90}


def _fetch_history(date_filter="All time", type_filter="All types", grade_filter="All grades"):
    try:
        resp = httpx.get(f"{API_BASE}/sessions/list", timeout=10).raise_for_status().json()
        sessions = resp["sessions"]
    except Exception:
        sessions = []

    if date_filter != "All time":
        days = _DATE_FILTER_DAYS[date_filter]
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        filtered = []
        for s in sessions:
            ca = s.get("created_at") or ""
            try:
                if ca:
                    dt = datetime.fromisoformat(ca.replace("Z", "+00:00"))
                    if dt.tzinfo is None:  # stored as naive UTC
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt >= cutoff:
                        filtered.append(s)
            except ValueError:
                pass
        sessions = filtered

    if type_filter != "All types":
        sessions = [s for s in sessions if s.get("interview_type") == type_filter]

    if grade_filter != "All grades":
        sessions = [s for s in sessions if s.get("grade") == grade_filter]

    return history_html(sessions)


def _show(page: int):
    """4-tuple of gr.update(visible) — only page `page` is shown (0-3)."""
    return tuple(gr.update(visible=(i == page)) for i in range(4))


# ── Pure navigation handlers (only return _show — no content) ─────────────────

def go_to_setup():    return _show(1)
def go_to_history():  return _show(0)
def go_to_interview(): return _show(2)
def go_to_report():   return _show(3)

def go_to_interview_if_valid(role):
    if not role.strip():
        return _show(1) + (warning_html("Please enter a Target Role before starting the interview."),)
    return _show(2) + ("",)

def go_to_report_if_selected(clicked: str):
    session_id = (clicked or "").split(":")[0]
    if not session_id:
        return _show(0)
    return _show(3)


# ── Content handlers (no column visibility mixing) ────────────────────────────

def load_history(date_filter="All time", type_filter="All types", grade_filter="All grades"):
    return _fetch_history(date_filter, type_filter, grade_filter)


def view_past_report_content(clicked: str):
    session_id = (clicked or "").split(":")[0]
    if not session_id:
        return gr.update()
    resp = httpx.get(
        f"{API_BASE}/session/{session_id}/report", timeout=10
    ).raise_for_status().json()
    return report_html(resp)


def start_interview(role, interview_type, difficulty, jd_text, num_questions):
    """Load interview content. Navigation handled by go_to_interview_if_valid."""
    global _session_id, _current_question, _question_num, _max_questions

    if not role.strip():
        return ("",) * 6  # navigation already stayed on setup, return empty

    try:
        resp = httpx.post(f"{API_BASE}/session/create", json={
            "role": role, "interview_type": interview_type,
            "difficulty": difficulty, "jd_text": jd_text,
            "num_questions": int(num_questions),
        }, timeout=30).raise_for_status().json()
    except Exception as e:
        return (warning_html(f"Could not connect to interview service: {e}"),) + ("",) * 5

    _session_id       = resp["session_id"]
    _current_question = resp["first_question"]
    _question_num     = 1
    _max_questions    = resp.get("max_questions") or QUESTIONS_PER_TYPE[interview_type]

    audio_path = _speak(_current_question, "opening")

    return (
        progress_html(_question_num, _max_questions),
        question_html(_current_question, _question_num),
        audio_path,
        None,
        "",
        "",
    )  # 6 items — interview_outputs only


def submit_answer(audio_input):
    """Returns (done_flag, ...interview_outputs). Navigation via gr.State.change."""
    global _current_question, _question_num

    if _session_id is None:
        raise gr.Error("No active session.")
    if audio_input is None:
        return (
            False,
            gr.update(), gr.update(), gr.update(), gr.update(),
            warning_html("Please stop the recording first, then click Submit Answer."),
            gr.update(),
        )

    with open(audio_input, "rb") as f:
        tr = httpx.post(
            f"{API_BASE}/session/transcribe",
            files={"file": (Path(audio_input).name, f)},
            timeout=30,
        ).raise_for_status().json()

    transcript = tr.pop("transcript")

    resp = httpx.post(f"{API_BASE}/session/answer", json={
        "session_id": _session_id,
        "transcript": transcript,
        "speech_metrics": tr,
    }, timeout=60).raise_for_status().json()

    if resp["done"]:
        return (True,) + _interview_done_content(resp["report"])

    _current_question = resp["next_question"]
    _question_num += 1
    audio_path = _speak(_current_question, "followup")

    return (
        False,
        progress_html(_question_num, _max_questions),
        question_html(_current_question, _question_num),
        audio_path,
        None,
        score_html(resp["scores"]),
        "",
    )


def end_interview(audio_input):
    """End & Get Report. Submits any pending audio first; shows placeholder if no answers."""
    global _session_id, _current_question, _question_num

    if _session_id is None:
        return (False,) + (gr.update(),) * 6

    has_answers = _question_num > 1

    # Submit pending audio recording before ending
    if audio_input is not None:
        try:
            with open(audio_input, "rb") as f:
                tr = httpx.post(
                    f"{API_BASE}/session/transcribe",
                    files={"file": (Path(audio_input).name, f)},
                    timeout=30,
                ).raise_for_status().json()
            transcript = tr.pop("transcript")
            resp = httpx.post(f"{API_BASE}/session/answer", json={
                "session_id": _session_id,
                "transcript": transcript,
                "speech_metrics": tr,
            }, timeout=60).raise_for_status().json()
            _question_num += 1
            has_answers = True
            if resp.get("done"):
                return (True,) + _interview_done_content(resp["report"])
        except Exception:
            pass

    # No answers recorded at all — show placeholder instead of erroring
    if not has_answers:
        _session_id = None
        _current_question = ""
        _question_num = 0
        return (True, "", "", None, None, "", no_answers_html())

    try:
        resp = httpx.post(
            f"{API_BASE}/session/end", json={"session_id": _session_id}, timeout=60
        ).raise_for_status().json()
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Could not end interview.")
        raise gr.Error(detail)
    return (True,) + _interview_done_content(resp["report"])


def _interview_done_content(report: dict):
    """Returns 6-tuple for interview_outputs (report in report_display)."""
    global _session_id, _current_question, _question_num
    _session_id = None
    _current_question = ""
    _question_num = 0
    return "", "", None, None, "", report_html(report)


def _speak(text: str, tag: str) -> str | None:
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False, prefix=f"iq_{tag}_") as f:
            out = synthesize_speech(text, f.name)
        return str(out)
    except Exception:
        return None


def delete_past_session(clicked: str, date_filter, type_filter, grade_filter):
    session_id = (clicked or "").split(":")[0]
    if session_id:
        try:
            httpx.delete(f"{API_BASE}/session/{session_id}", timeout=10).raise_for_status()
        except Exception:
            pass
    return _fetch_history(date_filter, type_filter, grade_filter)


# ── UI layout ─────────────────────────────────────────────────────────────────

_PAGE_JS = """
function _iqTrigger(elemId, value) {
  var wrapper = document.getElementById(elemId);
  console.log('[IQ] _iqTrigger', elemId, '→ wrapper:', wrapper);
  if (!wrapper) { console.error('[IQ] wrapper not found for', elemId); return; }
  var el = wrapper.querySelector('textarea');
  console.log('[IQ] textarea:', el);
  if (!el) { console.error('[IQ] textarea not found inside', elemId); return; }
  el.value = value;
  el.dispatchEvent(new Event('input', {bubbles: true}));
  el.dispatchEvent(new Event('change', {bubbles: true}));
  console.log('[IQ] dispatched events for', elemId, 'value=', value);
}

document.addEventListener('click', function(e) {
  var del = e.target.closest('[data-iq-del]');
  if (del) {
    e.stopPropagation();
    var sid = del.getAttribute('data-iq-del');
    console.log('[IQ] delete clicked, sid=', sid);
    if (!confirm('Delete this interview report? This cannot be undone.')) return;
    _iqTrigger('iq_delete_session', sid + ':' + Date.now());
    return;
  }
  var card = e.target.closest('[data-iq-sid]');
  if (card) {
    var sid = card.getAttribute('data-iq-sid');
    console.log('[IQ] card clicked, sid=', sid);
    _iqTrigger('iq_click_session', sid + ':' + Date.now());
  }
}, true);
"""

with gr.Blocks(title="PrepWise AI") as demo:

    # ── Page 0: History ────────────────────────────────────────────────────────
    with gr.Column(visible=True) as history_page:
        with gr.Column(elem_classes="page-wrap"):
            gr.HTML("""
            <div class="app-header">
              <div class="app-title">PrepWise AI</div>
              <div class="app-subtitle">AI-Powered Interviews · Instant Feedback · Actionable Insights</div>
            </div>""")

            gr.HTML("""
            <style>
            .iq-card:hover {
              background: #f5f3ff !important;
              border-color: #a5b4fc !important;
              transform: translateY(-1px);
              box-shadow: 0 4px 16px rgba(99,102,241,.14) !important;
            }
            .iq-del:hover { background:#fee2e2 !important; color:#dc2626 !important; border-color:#fca5a5 !important; }
            </style>""")

            history_new_btn = gr.Button("＋  New Interview", variant="primary", size="lg")

            gr.HTML('<div class="section-label" style="margin-top:28px;">Past Interviews</div>')

            with gr.Row():
                filter_date = gr.Dropdown(
                    ["All time", "Last 7 days", "Last 30 days", "Last 3 months"],
                    value="All time", label="Date", scale=1,
                )
                filter_type = gr.Dropdown(
                    ["All types"] + INTERVIEW_TYPES,
                    value="All types", label="Type", scale=1,
                )
                filter_grade = gr.Dropdown(
                    ["All grades", "A+", "A", "B", "C", "D", "F"],
                    value="All grades", label="Grade", scale=1,
                )

            history_cards = gr.HTML()
            clicked_session_id = gr.Textbox(elem_id="iq_click_session", show_label=False, container=False)
            delete_session_id  = gr.Textbox(elem_id="iq_delete_session", show_label=False, container=False)

    # ── Page 1: Setup ──────────────────────────────────────────────────────────
    with gr.Column(visible=True) as setup_page:
        with gr.Column(elem_classes="page-wrap"):
            gr.HTML("""
            <div class="app-header">
              <div class="app-title">PrepWise AI</div>
              <div class="app-subtitle">AI-Powered Interviews · Instant Feedback · Actionable Insights</div>
            </div>""")

            with gr.Column(elem_classes="card"):
                gr.HTML('<div class="section-label">Your Details</div>')
                with gr.Row():
                    role_input = gr.Textbox(
                        label="Target Role",
                        placeholder="e.g. Senior Backend Engineer",
                        scale=2,
                    )
                    diff_input = gr.Dropdown(
                        DIFFICULTY_LEVELS, label="Difficulty", value="Mid", scale=1,
                    )

                gr.HTML('<div class="section-label">Interview Type</div>')
                type_input = gr.Radio(INTERVIEW_TYPES, label="Interview Type", show_label=False, value="Technical")

                num_questions_input = gr.Number(
                    value=QUESTIONS_PER_TYPE["Technical"],
                    label="Session Question Limit",
                    minimum=1, maximum=15, precision=0,
                )

                gr.HTML('<div class="section-label">Job Description (optional)</div>')
                jd_input = gr.Textbox(
                    label="Job Description",
                    show_label=False,
                    placeholder="Paste the job description here to get personalised questions tailored to the role…",
                    lines=5,
                )

                setup_warning = gr.HTML()

                with gr.Row():
                    setup_back_btn = gr.Button("← History", variant="secondary", scale=1)
                    start_btn      = gr.Button("🚀  Start Interview", variant="primary", scale=3)

    # ── Page 2: Interview ──────────────────────────────────────────────────────
    with gr.Column(visible=True) as interview_page:
        with gr.Column(elem_classes="page-wrap"):
            with gr.Column(elem_classes="card"):
                gr.HTML("""
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                  <span style="font-size:1.2rem;font-weight:800;color:#0f172a;">Live Interview</span>
                  <span style="font-size:.8rem;color:#94a3b8;font-weight:600;letter-spacing:.06em;text-transform:uppercase;">PrepWise AI</span>
                </div>""")

                progress_display = gr.HTML()
                question_display = gr.HTML()

                gr.HTML('<div class="section-label">🔊 Listen to question</div>')
                question_audio = gr.Audio(label="Question Audio", show_label=False, autoplay=True)

                gr.HTML('<div class="section-label">🎙️ Record your answer</div>')
                mic_input = gr.Audio(sources=["microphone"], type="filepath", label="Answer", show_label=False)

                score_display = gr.HTML()

                with gr.Row():
                    submit_btn         = gr.Button("Submit Answer ➜", variant="primary", scale=3)
                    stop_btn           = gr.Button("⏹  End & Get Report", variant="stop", scale=2)
                    interview_back_btn = gr.Button("✕  Cancel", variant="secondary", scale=1)

    # ── Page 3: Report ─────────────────────────────────────────────────────────
    with gr.Column(visible=True) as report_page:
        with gr.Column(elem_classes="page-wrap"):
            report_display = gr.HTML()
            with gr.Row(elem_classes="card"):
                back_to_history_btn = gr.Button("← History", variant="secondary", scale=1)
                new_interview_btn   = gr.Button("🔄  New Interview", variant="primary", scale=3)

    # ── State: submit done → navigate to report ───────────────────────────────
    _done_flag = gr.State(value=False)

    # ── Output groups ──────────────────────────────────────────────────────────
    pages             = [history_page, setup_page, interview_page, report_page]
    interview_outputs = [progress_display, question_display, question_audio, mic_input, score_display, report_display]
    history_outputs   = [history_cards]
    filter_inputs     = [filter_date, filter_type, filter_grade]

    # ── Pure navigation (History ↔ Setup) ─────────────────────────────────────
    history_new_btn.click(go_to_setup,        inputs=[], outputs=pages)
    new_interview_btn.click(go_to_setup,      inputs=[], outputs=pages)
    setup_back_btn.click(go_to_history,       inputs=[], outputs=pages)
    interview_back_btn.click(go_to_history,   inputs=[], outputs=pages)
    back_to_history_btn.click(go_to_history,  inputs=[], outputs=pages)

    # ── Back buttons also refresh history content ─────────────────────────────
    setup_back_btn.click(load_history,        inputs=filter_inputs, outputs=history_outputs)
    interview_back_btn.click(load_history,    inputs=filter_inputs, outputs=history_outputs)
    back_to_history_btn.click(load_history,   inputs=filter_inputs, outputs=history_outputs)

    # ── Filters update the card list ──────────────────────────────────────────
    filter_date.change(_fetch_history,  inputs=filter_inputs, outputs=history_outputs)
    filter_type.change(_fetch_history,  inputs=filter_inputs, outputs=history_outputs)
    filter_grade.change(_fetch_history, inputs=filter_inputs, outputs=history_outputs)

    # ── Click a history card → navigate to report ─────────────────────────────
    clicked_session_id.change(
        go_to_report_if_selected, inputs=[clicked_session_id], outputs=pages
    ).then(
        view_past_report_content, inputs=[clicked_session_id], outputs=[report_display]
    )

    # ── Delete a history card → remove and refresh list ───────────────────────
    delete_session_id.change(
        delete_past_session, inputs=[delete_session_id] + filter_inputs, outputs=history_outputs
    )

    # ── Slider default tracks interview type ─────────────────────────────────
    type_input.change(
        fn=lambda t: gr.update(value=QUESTIONS_PER_TYPE.get(t, 5)),
        inputs=[type_input], outputs=[num_questions_input],
    )

    # ── Navigate then load interview content ──────────────────────────────────
    start_btn.click(go_to_interview_if_valid, inputs=[role_input], outputs=pages + [setup_warning]).then(
        start_interview, inputs=[role_input, type_input, diff_input, jd_input, num_questions_input], outputs=interview_outputs
    )
    stop_btn.click(end_interview, inputs=[mic_input], outputs=[_done_flag] + interview_outputs)

    # ── Submit answer (conditional navigation via gr.State) ───────────────────
    submit_btn.click(submit_answer, inputs=[mic_input], outputs=[_done_flag] + interview_outputs)
    _done_flag.change(
        fn=lambda done: _show(3) if done else _show(2),
        inputs=[_done_flag], outputs=pages,
    )

    # ── On load: initialize all pages (forces Gradio to render them), then show only history ──
    demo.load(lambda: _show(0), inputs=None, outputs=pages)
    demo.load(load_history,     inputs=filter_inputs, outputs=history_outputs)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=GRADIO_PORT, share=False, css=CSS, js=_PAGE_JS)
