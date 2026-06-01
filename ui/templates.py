"""HTML template functions for the PrepWise AI UI."""

_GRADE_STYLE = {
    "A+": ("#065f46", "#d1fae5"), "A": ("#065f46", "#d1fae5"),
    "B":  ("#1e40af", "#dbeafe"), "C": ("#92400e", "#fef3c7"),
    "D":  ("#991b1b", "#fee2e2"), "F": ("#7f1d1d", "#fecaca"),
}


def warning_html(message: str) -> str:
    return f"""
<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;padding:14px 18px;
            display:flex;align-items:center;gap:12px;margin-top:8px;">
  <span style="font-size:1.2rem;">⚠️</span>
  <span style="color:#9a3412;font-weight:600;font-size:.9rem;">{message}</span>
</div>"""


def progress_html(current: int, total: int) -> str:
    pct = int((current - 1) / total * 100)
    return f"""
<div style="margin:0 0 4px;">
  <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
    <span style="font-size:.82rem;font-weight:600;color:#64748b;letter-spacing:.02em;">
      QUESTION {current} OF {total}
    </span>
    <span style="font-size:.82rem;font-weight:700;color:#6366f1;">{pct}% complete</span>
  </div>
  <div style="background:#e2e8f0;border-radius:999px;height:7px;overflow:hidden;">
    <div style="background:linear-gradient(90deg,#6366f1,#a78bfa);width:{pct}%;height:7px;border-radius:999px;transition:width .4s ease;"></div>
  </div>
</div>"""


def question_html(question: str, num: int) -> str:
    return f"""
<div style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);border-radius:18px;padding:28px 32px;box-shadow:0 8px 32px rgba(99,102,241,.28);">
  <div style="font-size:.7rem;font-weight:700;letter-spacing:.12em;color:rgba(255,255,255,.65);text-transform:uppercase;margin-bottom:10px;">
    Question {num}
  </div>
  <div style="font-size:1.12rem;font-weight:500;color:#fff;line-height:1.75;">
    {question}
  </div>
</div>"""


def score_html(scores: dict) -> str:
    overall = scores.get("overall_score", 0)
    color = "#10b981" if overall >= 7 else "#f59e0b" if overall >= 5 else "#ef4444"
    return f"""
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px 18px;display:flex;align-items:center;gap:14px;">
  <div style="background:{color}18;border-radius:50%;width:50px;height:50px;display:flex;align-items:center;justify-content:center;flex-shrink:0;border:2px solid {color}40;">
    <span style="font-size:1.15rem;font-weight:800;color:{color};">{overall}</span>
  </div>
  <div>
    <div style="font-weight:700;color:#0f172a;font-size:.92rem;">Answer submitted ✓</div>
    <div style="color:#64748b;font-size:.82rem;margin-top:3px;">
      Clarity {scores.get('communication_clarity', 0)}/10 &nbsp;·&nbsp;
      Depth {scores.get('depth_of_answer', 0)}/10 &nbsp;·&nbsp;
      Accuracy {scores.get('technical_accuracy', 0)}/10
    </div>
  </div>
</div>"""


def history_html(sessions: list) -> str:
    if not sessions:
        return """
<div style="text-align:center;padding:48px 20px;">
  <div style="font-size:2.8rem;margin-bottom:14px;">📋</div>
  <div style="font-size:1rem;font-weight:600;color:#64748b;">No interviews found</div>
  <div style="font-size:.88rem;color:#94a3b8;margin-top:8px;">
    Try adjusting the filters above, or complete your first mock interview.
  </div>
</div>"""

    n = len(sessions)
    count_line = (
        f'<div style="font-size:.78rem;font-weight:600;color:#94a3b8;letter-spacing:.04em;'
        f'text-transform:uppercase;margin-bottom:12px;">'
        f'{n} interview{"s" if n != 1 else ""}</div>'
    )

    cards = ""
    for s in sessions:
        grade = s.get("grade", "?")
        fc, bc = _GRADE_STYLE.get(grade, ("#1e293b", "#f1f5f9"))
        score = s.get("overall_score", 0)
        score_c = "#10b981" if score >= 7 else "#f59e0b" if score >= 5 else "#ef4444"
        date_str = (s.get("created_at") or "")[:10] or "–"
        q_count = s.get("question_count", 0)
        sid = s["session_id"]
        cards += f"""
<div class="iq-card" data-iq-sid="{sid}"
     style="background:#fff;border:1.5px solid #e2e8f0;border-radius:16px;padding:18px 22px;
            display:flex;align-items:center;gap:16px;margin-bottom:10px;cursor:pointer;
            box-shadow:0 2px 8px rgba(0,0,0,.04);transition:all .15s ease;">
  <div style="background:{bc};color:{fc};font-size:1.25rem;font-weight:900;width:52px;height:52px;
              border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
    {grade}
  </div>
  <div style="flex:1;min-width:0;">
    <div style="font-weight:700;color:#0f172a;font-size:.95rem;margin-bottom:4px;
                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
      {s.get('role', '–')}
    </div>
    <div style="color:#64748b;font-size:.8rem;">
      {s.get('interview_type','–')} &nbsp;·&nbsp; {s.get('difficulty','–')} &nbsp;·&nbsp; {q_count} Qs
    </div>
  </div>
  <div style="text-align:right;flex-shrink:0;display:flex;align-items:center;gap:12px;">
    <div>
      <div style="font-size:1.3rem;font-weight:800;color:{score_c};">
        {score}<span style="font-size:.75rem;font-weight:500;color:#94a3b8;">/10</span>
      </div>
      <div style="font-size:.72rem;color:#94a3b8;margin-top:3px;">{date_str}</div>
    </div>
    <div style="color:#c7d2fe;font-size:1.5rem;font-weight:300;line-height:1;">›</div>
    <div class="iq-del" data-iq-del="{sid}"
         style="cursor:pointer;background:#fef2f2;color:#fca5a5;border:1px solid #fecaca;
                border-radius:8px;padding:5px 10px;font-size:.85rem;
                flex-shrink:0;transition:all .15s ease;line-height:1.4;">
      🗑
    </div>
  </div>
</div>"""
    return count_line + cards


def no_answers_html() -> str:
    return """
<div style="font-family:'Inter',system-ui,sans-serif;max-width:760px;margin:0 auto;padding:4px 0 24px;">
  <div style="text-align:center;padding:72px 24px;">
    <div style="font-size:3rem;margin-bottom:18px;">📋</div>
    <div style="font-size:1.45rem;font-weight:800;color:#0f172a;margin-bottom:10px;">No Report Available</div>
    <div style="color:#64748b;font-size:.95rem;line-height:1.75;">
      No answers were recorded during this session.<br>
      Answer at least one question to receive a full performance report.
    </div>
  </div>
</div>"""


def report_html(report: dict) -> str:
    grade = report["grade"]
    overall = report["overall_score"]

    fc, bc = _GRADE_STYLE.get(grade, ("#1e293b", "#f1f5f9"))

    bars = _dimension_bars(report["dimension_averages"])
    qa_rows = _qa_breakdown(report["per_question_breakdown"])

    wpm = report["avg_wpm"]
    filler = report["avg_filler_rate"]
    wpm_c = "#10b981" if 120 <= wpm <= 150 else "#f59e0b"
    filler_c = "#10b981" if filler <= 0.05 else "#ef4444"

    return f"""
<div style="font-family:'Inter',system-ui,sans-serif;max-width:760px;margin:0 auto;padding:4px 0 24px;">

  <div style="text-align:center;padding:32px 0 28px;">
    <div style="display:inline-flex;align-items:center;justify-content:center;background:{bc};color:{fc};font-size:2.8rem;font-weight:900;width:88px;height:88px;border-radius:50%;margin-bottom:18px;box-shadow:0 4px 24px rgba(0,0,0,.12);">
      {grade}
    </div>
    <div style="font-size:1.65rem;font-weight:800;color:#0f172a;margin-bottom:6px;">Interview Complete</div>
    <div style="color:#64748b;font-size:.95rem;">
      {report['role']} &nbsp;·&nbsp; {report['interview_type']} &nbsp;·&nbsp; {report['difficulty']}
    </div>
    <div style="margin-top:14px;display:inline-flex;gap:24px;justify-content:center;flex-wrap:wrap;">
      <div style="text-align:center;">
        <div style="font-size:1.5rem;font-weight:800;color:#6366f1;">{overall}<span style="font-size:.9rem;font-weight:500;color:#94a3b8;">/10</span></div>
        <div style="font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#94a3b8;margin-top:2px;">Overall Score</div>
      </div>
      <div style="width:1px;background:#e2e8f0;"></div>
      <div style="text-align:center;">
        <div style="font-size:1.5rem;font-weight:800;color:#0f172a;">{len(report['per_question_breakdown'])}</div>
        <div style="font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#94a3b8;margin-top:2px;">Questions Asked</div>
      </div>
    </div>
  </div>

  <div style="background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:24px 28px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,.04);">
    <div style="font-size:.95rem;font-weight:700;color:#0f172a;margin-bottom:20px;">📊 Dimension Scores</div>
    {bars}
  </div>

  <div style="background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:24px 28px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,.04);">
    <div style="font-size:.95rem;font-weight:700;color:#0f172a;margin-bottom:18px;">🎙️ Speech Metrics</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
      <div style="text-align:center;background:#f8fafc;border-radius:12px;padding:18px 12px;border:1px solid #e2e8f0;">
        <div style="font-size:2.1rem;font-weight:800;color:{wpm_c};">{wpm}</div>
        <div style="font-size:.78rem;color:#64748b;margin-top:5px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Words / Min</div>
        <div style="font-size:.75rem;color:#94a3b8;margin-top:2px;">ideal 120 – 150</div>
      </div>
      <div style="text-align:center;background:#f8fafc;border-radius:12px;padding:18px 12px;border:1px solid #e2e8f0;">
        <div style="font-size:2.1rem;font-weight:800;color:{filler_c};">{filler:.1%}</div>
        <div style="font-size:.78rem;color:#64748b;margin-top:5px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;">Filler Rate</div>
        <div style="font-size:.75rem;color:#94a3b8;margin-top:2px;">ideal &lt; 5%</div>
      </div>
    </div>
  </div>

  <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:16px;padding:24px 28px;margin-bottom:16px;box-shadow:0 8px 28px rgba(99,102,241,.25);">
    <div style="font-size:.95rem;font-weight:700;color:#fff;margin-bottom:14px;">💡 Coaching Recommendations</div>
    <div style="font-size:.88rem;color:rgba(255,255,255,.92);line-height:1.85;white-space:pre-line;">{report['coaching_recommendations']}</div>
  </div>

  <div style="background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:24px 28px;box-shadow:0 2px 8px rgba(0,0,0,.04);">
    <div style="font-size:.95rem;font-weight:700;color:#0f172a;margin-bottom:18px;">📝 Per-Question Breakdown</div>
    {qa_rows}
  </div>

</div>"""


# ── Private helpers ───────────────────────────────────────────────────────────

def _score_color(score: float) -> str:
    return "#10b981" if score >= 7 else "#f59e0b" if score >= 5 else "#ef4444"


def _dimension_bars(dimension_averages: dict) -> str:
    bars = ""
    for dim, score in dimension_averages.items():
        label = dim.replace("_", " ").title()
        pct = int(score / 10 * 100)
        c = _score_color(score)
        bars += f"""
  <div style="margin-bottom:14px;">
    <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
      <span style="font-size:.875rem;color:#374151;font-weight:500;">{label}</span>
      <span style="font-size:.875rem;font-weight:700;color:{c};">{score}/10</span>
    </div>
    <div style="background:#e5e7eb;border-radius:999px;height:8px;">
      <div style="background:{c};width:{pct}%;height:8px;border-radius:999px;"></div>
    </div>
  </div>"""
    return bars


def _qa_breakdown(per_question: list) -> str:
    rows = ""
    for i, qa in enumerate(per_question):
        s = qa["scores"]
        o = s.get("overall_score", 0)
        c = _score_color(o)
        rows += f"""
  <div style="border:1px solid #e5e7eb;border-radius:12px;padding:18px 20px;margin-bottom:12px;background:#fafafa;">

    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;">
      <div style="font-weight:600;color:#1e293b;font-size:.93rem;line-height:1.55;flex:1;">
        Q{i + 1}: {qa['question']}
      </div>
      <div style="background:{c}18;color:{c};font-weight:800;font-size:.9rem;padding:3px 12px;
                  border-radius:999px;white-space:nowrap;flex-shrink:0;border:1.5px solid {c}40;">
        {o}/10
      </div>
    </div>

    <details style="margin-bottom:10px;">
      <summary style="cursor:pointer;font-size:.85rem;font-weight:600;color:#4f46e5;
                      list-style:none;display:flex;align-items:center;gap:6px;
                      padding:8px 12px;background:#eef2ff;border-radius:8px;
                      user-select:none;">
        <span style="font-size:.75rem;">▶</span> View your answer
      </summary>
      <div style="margin-top:8px;padding:12px 14px;background:#fff;border-radius:8px;
                  border:1px solid #e5e7eb;font-size:.85rem;color:#374151;line-height:1.7;">
        {qa['answer']}
      </div>
    </details>

    <div style="background:#fff;border-radius:8px;padding:10px 14px;
                border-left:3px solid {c};font-size:.85rem;color:#475569;line-height:1.6;">
      <strong style="color:#334155;">Feedback:</strong> {s.get('feedback', 'N/A')}
    </div>

  </div>"""
    return rows
