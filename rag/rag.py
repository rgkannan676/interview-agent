"""RAG pipeline — question bank loader, JD ingestion, and ChromaDB retrieval."""

import hashlib
import yaml
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import QUESTION_BANK_DIR, CHROMA_DB_DIR, EMBEDDING_MODEL

_embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
_chroma = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))

QUESTION_COLLECTION = "question_bank"
JD_COLLECTION = "job_descriptions"
_INDEX_MARKER = CHROMA_DB_DIR / ".qbank_hash"


# ---------- Question Bank ----------

def load_question_bank() -> list[dict]:
    """Load all YAML question files from the question bank directory."""
    questions = []
    for path in sorted(QUESTION_BANK_DIR.glob("*.yaml")):
        with open(path) as f:
            questions.extend(yaml.safe_load(f) or [])
    return questions


def _qbank_hash() -> str:
    """SHA-256 of all YAML file contents — changes when questions are added/edited."""
    h = hashlib.sha256()
    for path in sorted(QUESTION_BANK_DIR.glob("*.yaml")):
        h.update(path.read_bytes())
    return h.hexdigest()


def index_question_bank():
    """Index the question bank into ChromaDB.

    Skips entirely if the YAML files haven't changed since the last index run.
    To force a reindex, delete data/chroma_db/.qbank_hash.
    """
    current_hash = _qbank_hash()
    if _INDEX_MARKER.exists() and _INDEX_MARKER.read_text().strip() == current_hash:
        return  # nothing changed — skip

    collection = _chroma.get_or_create_collection(
        QUESTION_COLLECTION, embedding_function=_embedding_fn
    )
    questions = load_question_bank()
    if not questions:
        return

    existing_ids = set(collection.get()["ids"])
    new_docs, new_ids, new_metas = [], [], []
    for q in questions:
        qid = q.get("id", q["question"][:64])
        if qid not in existing_ids:
            new_docs.append(q["question"])
            new_ids.append(qid)
            new_metas.append({
                "type": q.get("type", ""),
                "difficulty": q.get("difficulty", ""),
            })

    if new_docs:
        collection.add(documents=new_docs, ids=new_ids, metadatas=new_metas)

    _INDEX_MARKER.parent.mkdir(parents=True, exist_ok=True)
    _INDEX_MARKER.write_text(current_hash)


def retrieve_questions(
    query: str,
    interview_type: str,
    difficulty: str = "",
    n_results: int = 5,
) -> list[str]:
    """Retrieve relevant questions from ChromaDB given a query."""
    collection = _chroma.get_or_create_collection(
        QUESTION_COLLECTION, embedding_function=_embedding_fn
    )

    def _query(where):
        return collection.query(query_texts=[query], n_results=n_results, where=where)

    def _docs(r):
        return r["documents"][0] if r["documents"] else []

    # Most specific first, progressively broader
    if interview_type and difficulty:
        docs = _docs(_query({"$and": [{"type": {"$eq": interview_type}}, {"difficulty": {"$eq": difficulty}}]}))
        if docs:
            return docs
    if interview_type:
        docs = _docs(_query({"type": {"$eq": interview_type}}))
        if docs:
            return docs
    return _docs(_query(None))


# ---------- Job Description ----------

_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)


def ingest_job_description(session_id: str, jd_text: str):
    """Chunk and store a job description in ChromaDB under the given session_id."""
    collection = _chroma.get_or_create_collection(
        JD_COLLECTION, embedding_function=_embedding_fn
    )
    chunks = _splitter.split_text(jd_text)
    ids = [f"{session_id}_chunk_{i}" for i in range(len(chunks))]
    metas = [{"session_id": session_id}] * len(chunks)
    collection.add(documents=chunks, ids=ids, metadatas=metas)


def retrieve_jd_context(session_id: str, query: str, n_results: int = 3) -> str:
    """Retrieve JD chunks relevant to a query for the given session."""
    collection = _chroma.get_or_create_collection(
        JD_COLLECTION, embedding_function=_embedding_fn
    )
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where={"session_id": session_id},
    )
    chunks = results["documents"][0] if results["documents"] else []
    return "\n\n".join(chunks)
