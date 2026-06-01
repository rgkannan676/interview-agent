from pathlib import Path
from dotenv import load_dotenv

# --- Paths ---
BASE_DIR = Path(__file__).parent

load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data"
QUESTION_BANK_DIR = DATA_DIR / "question_bank"
JD_UPLOADS_DIR = DATA_DIR / "jd_uploads"
SESSIONS_DIR = DATA_DIR / "sessions"
CHROMA_DB_DIR = DATA_DIR / "chroma_db"
MLFLOW_TRACKING_URI = str(BASE_DIR / "mlruns")

# --- Groq ---
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_WHISPER_MODEL = "whisper-large-v3"

# --- Embeddings ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Interview ---
QUESTIONS_PER_TYPE = {
    "Technical": 6,
    "Behavioural": 5,
    "System Design": 4,
}

DIFFICULTY_LEVELS = ["Junior", "Mid", "Senior", "Principal"]
INTERVIEW_TYPES = list(QUESTIONS_PER_TYPE.keys())

# --- Speech Metrics ---
IDEAL_WPM_MIN = 120
IDEAL_WPM_MAX = 150
FILLER_WORDS = {"um", "uh", "like", "basically", "you know"}
IDEAL_FILLER_RATE_MAX = 0.05  # 5%

# --- Evaluation Dimensions ---
DIMENSIONS = [
    "technical_accuracy",
    "communication_clarity",
    "star_compliance",
    "depth_of_answer",
    "confidence_signal",
    "conciseness",
]

# Weights per interview type (must sum to 1.0)
DIMENSION_WEIGHTS = {
    "Technical": {
        "technical_accuracy": 0.40,
        "communication_clarity": 0.15,
        "star_compliance": 0.05,
        "depth_of_answer": 0.20,
        "confidence_signal": 0.10,
        "conciseness": 0.10,
    },
    "Behavioural": {
        "technical_accuracy": 0.10,
        "communication_clarity": 0.20,
        "star_compliance": 0.35,
        "depth_of_answer": 0.15,
        "confidence_signal": 0.10,
        "conciseness": 0.10,
    },
    "System Design": {
        "technical_accuracy": 0.30,
        "communication_clarity": 0.15,
        "star_compliance": 0.05,
        "depth_of_answer": 0.30,
        "confidence_signal": 0.10,
        "conciseness": 0.10,
    },
}

# --- Gradio / API ---
API_HOST = "0.0.0.0"
API_PORT = 8000
GRADIO_PORT = 7860
