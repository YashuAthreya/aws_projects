import os
import json
from dotenv import load_dotenv
import faiss
import numpy as np
from openai import OpenAI
from sqlalchemy import text

try:
    from .database import SessionLocal
except ImportError:  # allows running this file directly as a script
    from database import SessionLocal


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

EMBEDDING_MODEL = "text-embedding-3-small"

FAISS_INDEX_FILE_USER = "data/user_faiss.index"
FAISS_INDEX_FILE_ADMIN = "data/admin_faiss.index"

load_dotenv()
client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)


# ---------------------------------------------------------
# Create embedding
# ---------------------------------------------------------

def create_embedding(text: str) -> np.ndarray:

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )

    embedding = response.data[0].embedding

    return np.array(
        embedding,
        dtype=np.float32
    )


# ---------------------------------------------------------
# Initialize FAISS
# ---------------------------------------------------------

def create_index():

    # text-embedding-3-small produces 1536-dimensional
    # embeddings by default.
    dimension = 1536

    base_index = faiss.IndexFlatL2(dimension)

    # Allows us to assign our own IDs to vectors.
    index = faiss.IndexIDMap(base_index)

    return index


 
def save_index(index,is_user:bool):
    
    FAISS_INDEX_FILE=FAISS_INDEX_FILE_USER if is_user else FAISS_INDEX_FILE_ADMIN

    os.makedirs("data", exist_ok=True)

    faiss.write_index(
        index,
        FAISS_INDEX_FILE
    )


# ---------------------------------------------------------
# Load FAISS index
# ---------------------------------------------------------

def load_index(is_user:bool):
    
    FAISS_INDEX_FILE=FAISS_INDEX_FILE_USER if is_user else FAISS_INDEX_FILE_ADMIN

    if not os.path.exists(FAISS_INDEX_FILE):
        return create_index()

    return faiss.read_index(
        FAISS_INDEX_FILE
    )


# ---------------------------------------------------------
# Fetch embeddings from FAISS index
# ---------------------------------------------------------

def get_embedding(index, row_id):
    """
    Fetch a stored embedding for a specific row id from the FAISS index.

    IndexIDMap.reconstruct(id) is unimplemented in some faiss-cpu builds
    (e.g. Windows), so we reconstruct from the wrapped flat index by
    position instead, using id_map to translate external id -> position.
    """
    base_index = getattr(index, "index", index)

    try:
        ids = list_indexed_ids(index)
        position = ids.index(int(row_id))
        embedding = base_index.reconstruct(position)
    except Exception as exc:
        raise ValueError(f"Could not fetch embedding for row_id={row_id}") from exc

    return np.asarray(embedding, dtype=np.float32)


def get_embeddings(index, row_ids):
    """
    Fetch multiple stored embeddings for the given row ids.
    Returns a 2D numpy array shaped (n, embedding_dim).
    """
    if not row_ids:
        return np.empty((0, 0), dtype=np.float32)

    vectors = [get_embedding(index, row_id) for row_id in row_ids]
    return np.vstack(vectors).astype(np.float32)


def list_indexed_ids(index) -> list[int]:
    """Return every external row id currently stored in a FAISS IndexIDMap."""
    if index.ntotal == 0:
        return []

    return [int(row_id) for row_id in faiss.vector_to_array(index.id_map)]


# ---------------------------------------------------------
# Combine Postgres rows with their FAISS embedding info
# ---------------------------------------------------------

def get_user_embedding_records(db) -> list[dict]:

    index = load_index(True)
    indexed_ids = set(list_indexed_ids(index))

    records = []
    for row in fetch_users(db):
        user_id = row["user_id"]
        has_embedding = user_id in indexed_ids

        embedding_dim = None
        embedding_preview = None
        if has_embedding:
            vector = get_embedding(index, user_id)
            embedding_dim = int(vector.shape[0])
            embedding_preview = [round(float(value), 4) for value in vector[:5]]

        records.append({
            "user_id": user_id,
            "user_name": row["user_name"],
            "user_email": row["user_email"],
            "mobile_number": row["mobile_number"],
            "resume_loc": row["resume_loc"],
            "has_embedding": has_embedding,
            "embedding_dim": embedding_dim,
            "embedding_preview": embedding_preview,
        })

    return records


def get_job_embedding_records(db) -> list[dict]:

    index = load_index(False)
    indexed_ids = set(list_indexed_ids(index))

    records = []
    for row in fetch_job_postings(db, only_pending=False):
        job_id = row["id"]
        has_embedding = job_id in indexed_ids

        details = row["details"]
        if isinstance(details, str):
            details = json.loads(details)
        details = details or {}

        embedding_dim = None
        embedding_preview = None
        if has_embedding:
            vector = get_embedding(index, job_id)
            embedding_dim = int(vector.shape[0])
            embedding_preview = [round(float(value), 4) for value in vector[:5]]

        records.append({
            "id": job_id,
            "title": details.get("title") or details.get("jobTitle"),
            "details": details,
            "is_active": row["is_active"],
            "emb_generated": row["emb_generated"],
            "has_embedding": has_embedding,
            "embedding_dim": embedding_dim,
            "embedding_preview": embedding_preview,
        })

    return records


# ---------------------------------------------------------
# Cosine similarity between user and job profile embeddings
# ---------------------------------------------------------

def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:

    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


def compute_job_match_scores(user_id: int, job_ids: list[int]) -> dict[int, float]:
    """
    Cosine similarity between a user's profile embedding and each job
    posting's embedding. Job ids without a stored embedding are skipped.
    """
    user_index = load_index(True)
    admin_index = load_index(False)

    try:
        user_vector = get_embedding(user_index, user_id)
    except ValueError:
        return {}

    scores = {}
    for job_id in job_ids:
        try:
            job_vector = get_embedding(admin_index, job_id)
        except ValueError:
            continue
        scores[job_id] = cosine_similarity(user_vector, job_vector)

    return scores


# ---------------------------------------------------------
# Insert ONE row
# ---------------------------------------------------------

def insert_row(
    index,
    row_id,
    text,
    original_row=None
):

    print(f"Creating embedding for row {row_id}")

    embedding = create_embedding(text)

    # FAISS expects shape:
    # (number_of_vectors, embedding_dimension)
    embedding = embedding.reshape(1, -1)
    print(f"Embedding shape for row {row_id}: {embedding.shape}={embedding}")

    # Convert your database ID to int64
    vector_id = np.array(
        [row_id],
        dtype=np.int64
    )

    # Add vector + your own ID
    index.add_with_ids(
        embedding,
        vector_id
    )

    print(
        f"Inserted row {row_id}. "
        f"Total vectors: {index.ntotal}"
    )


# ---------------------------------------------------------
# Search
# ---------------------------------------------------------

def search(
    index,
    query,
    k=5
):

    print(f"\nSearching for: {query}")

    query_embedding = create_embedding(query)
    query_embedding = query_embedding.reshape(
        1,
        -1
    )

    distances, ids = index.search(
        query_embedding,
        k
    )

    return distances, ids


# ---------------------------------------------------------
# Flatten a JSON/DB row into embeddable text
# ---------------------------------------------------------

def flatten_value(value) -> str:

    if value is None:
        return ""

    if isinstance(value, (list, tuple, set)):
        return ", ".join(flatten_value(item) for item in value if item not in (None, ""))

    if isinstance(value, dict):
        return "; ".join(
            f"{key}: {flatten_value(item)}"
            for key, item in value.items()
            if item not in (None, "", [], {})
        )

    return str(value).strip()


def build_user_text(row) -> str:

    parts = [
        f"name: {flatten_value(row['user_name'])}",
        f"email: {flatten_value(row['user_email'])}",
        f"resume: {flatten_value(row['resume_loc'])}",
    ]

    profile = row["job_profile"]
    if isinstance(profile, str):
        profile = json.loads(profile)
    if profile:
        parts.append(flatten_value(profile))

    return " | ".join(part for part in parts if part.split(": ", 1)[-1])


def build_job_posting_text(row) -> str:

    details = row["details"]
    if isinstance(details, str):
        details = json.loads(details)

    return flatten_value(details or {})


# ---------------------------------------------------------
# Fetch rows from Postgres
# ---------------------------------------------------------

def fetch_users(db):

    return db.execute(
        text(
            """
            SELECT user_id, user_name, user_email, mobile_number,
                   job_profile, resume_loc
            FROM user_table
            ORDER BY user_id
            """
        )
    ).mappings().all()


def fetch_job_postings(db, only_pending=True):

    where_clause = "WHERE is_active IS TRUE AND emb_generated IS FALSE" if only_pending else ""

    return db.execute(
        text(
            f"""
            SELECT id, details, is_active, emb_generated
            FROM job_posting
            {where_clause}
            ORDER BY id
            """
        )
    ).mappings().all()


def mark_job_postings_indexed(db, posting_ids):

    if not posting_ids:
        return

    db.execute(
        text(
            """
            UPDATE job_posting
            SET emb_generated = TRUE
            WHERE id = ANY(:ids)
            """
        ),
        {"ids": list(posting_ids)},
    )
    db.commit()


# ---------------------------------------------------------
# Index whole tables
# ---------------------------------------------------------

def index_users(db, index):

    indexed = 0

    for row in fetch_users(db):
        row_text = build_user_text(row)
        if not row_text:
            print(f"Skipping user {row['user_id']}: no text to embed")
            continue
        #print(f"Indexing user {row}")

        insert_row(index, row["user_id"], row_text)
        indexed += 1

    save_index(index, True)

    print(f"Indexed {indexed} users")
    return indexed


def index_pending_users(db, index):
    """Embed only users that are not yet present in the FAISS index."""
    indexed_ids = set(list_indexed_ids(index))
    indexed = 0

    for row in fetch_users(db):
        if row["user_id"] in indexed_ids:
            continue

        row_text = build_user_text(row)
        if not row_text:
            print(f"Skipping user {row['user_id']}: no text to embed")
            continue

        insert_row(index, row["user_id"], row_text)
        indexed += 1

    if indexed:
        save_index(index, True)

    print(f"Indexed {indexed} pending users")
    return indexed


def index_job_postings(db, index, only_pending=True):

    indexed_ids = []

    for row in fetch_job_postings(db, only_pending):
        #print(f"Indexing job posting {row}")
        row_text = build_job_posting_text(row)
        if not row_text:
            print(f"Skipping job posting {row['id']}: no text to embed")
            continue

        insert_row(index, row["id"], row_text)
        indexed_ids.append(row["id"])

    save_index(index, False)

    if only_pending:
        mark_job_postings_indexed(db, indexed_ids)

    print(f"Indexed {len(indexed_ids)} job postings")
    return len(indexed_ids)


# ---------------------------------------------------------
# Example
# ---------------------------------------------------------



def save_user_index(id, row_text):
    user_index = load_index(True)
    db = SessionLocal()
    try:
        #index_users(db, user_index)
        insert_row(user_index, id, row_text)
        save_index(user_index, True)

    finally:
        db.close()





if __name__ == "__main__":

    # Load existing indexes
    user_index = load_index(True)
    admin_index = load_index(False)

    db = SessionLocal()
    try:
        #index_users(db, user_index)
        index_job_postings(db, admin_index)
    finally:
        db.close()

