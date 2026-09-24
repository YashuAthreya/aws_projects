# app/user_router.py
#
# Candidate/user-facing endpoints: browsing jobs, registration, resume upload,
# profile completion, and the (unauthenticated, legacy) job-posting + user
# listing endpoints. Admin-only equivalents live under app/admin/router.py.

import json
import os
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from openai import OpenAI
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.index_gen import (
    compute_job_match_scores,
    get_job_embedding_records,
    get_user_embedding_records,
    insert_row,
    load_index,
    save_user_index,
    search as faiss_search,
)
from app.job_service import (
    build_job_posting_payload,
    create_job_posting_row,
    normalize_job_posting,
)
from app.models import User
from app.request_utils import parse_json_or_form
from app.user_service import build_user_filters

load_dotenv()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "../static")
S3_BUCKET = os.getenv("S3_BUCKET", "yv-resume-storage")
MAX_RESUME_SIZE_BYTES = 200 * 1024
MAX_RESUME_PAGES = 4

templates = Jinja2Templates(directory=STATIC_DIR)

router = APIRouter(tags=["User"])


@router.get("/")
def read_root(request: Request, db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            """
            SELECT id, details
            FROM job_posting
            WHERE is_active = TRUE     
            ORDER BY id DESC
            """
        )
    ).mappings().all()

    jobs = []
    for row in rows:
        details = row["details"] or {}
        job = normalize_job_posting(details)
        if job:
            job["id"] = row["id"]
            jobs.append(job)

    return templates.TemplateResponse("index.html", {"request": request, "jobs": jobs})


@router.get("/health")
def read_health():
    return {"message": "Healthy"}


@router.get("/jobs/match-scores")
def get_job_match_scores(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text(
            """
            SELECT id
            FROM job_posting
            WHERE is_active = TRUE
            """
        )
    ).mappings().all()

    job_ids = [row["id"] for row in rows]
    scores = compute_job_match_scores(current_user.user_id, job_ids)

    return {"scores": scores}


@router.get("/jobs/semantic-search")
def semantic_search_jobs(query: str, db: Session = Depends(get_db)):
    query = (query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="A search query is required.")

    admin_index = load_index(False)
    if admin_index.ntotal == 0:
        return {"query": query, "results": []}

    k = min(5, admin_index.ntotal)
    distances, ids = faiss_search(admin_index, query, k=k)

    candidate_ids = [int(job_id) for job_id in ids[0] if job_id != -1]
    if not candidate_ids:
        return {"query": query, "results": []}

    rows = db.execute(
        text(
            """
            SELECT id, details
            FROM job_posting
            WHERE id = ANY(:ids) AND is_active = TRUE
            """
        ),
        {"ids": candidate_ids},
    ).mappings().all()

    details_by_id = {row["id"]: row["details"] or {} for row in rows}

    results = []
    # Preserve FAISS's similarity ranking (ids/distances are already sorted, closest first).
    for job_id, distance in zip(ids[0], distances[0]):
        job_id = int(job_id)
        if job_id == -1 or job_id not in details_by_id:
            continue
        job = normalize_job_posting(details_by_id[job_id])
        job["id"] = job_id
        job["similarityDistance"] = float(distance)
        results.append(job)

    return {"query": query, "results": results}


@router.get("/embeddings")
def embeddings_view_page():
    return RedirectResponse(url="./../static/embeddings_view.html")


@router.get("/embeddings/users")
def list_user_embeddings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_user_embedding_records(db)


@router.get("/embeddings/jobs")
def list_job_embeddings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_job_embedding_records(db)


@router.get("/get_resume")
def ret_resume():
    return RedirectResponse(url="./../static/get_resume.html")


@router.get("/job_prof")
def job_prof():
    return RedirectResponse(url="./../static/job_prof.html")


@router.get("/job_posting")
def job_posting_page():
    print("\n\n\nServing job posting page\n\n\n")
    return RedirectResponse(url="./../static/job_posting.html")


@router.get("/job_postings_page")
def job_postings_list_page():
    return RedirectResponse(url="./../static/job_postings_list.html")


@router.get("/reg")
def ret_reg():
    return RedirectResponse(url="./../static/user_reg.html")


@router.get("/pdf")
def get_pdf(key: str = "InterviewSchedule.pdf"):
    s3_client = boto3.client("s3")
    response = s3_client.get_object(
        Bucket="yv-resume-storage",
        Key=key
    )

    return StreamingResponse(
        response["Body"],
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{key.split("/")[-1]}"'
        }
    )


def upload_pdf_to_s3(pdf_file: UploadFile, object_key: str) -> str:
    """Upload a PDF to S3 and return its S3 object key."""
    if pdf_file.content_type != "application/pdf" or not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    try:
        boto3.client("s3").upload_fileobj(
            pdf_file.file,
            S3_BUCKET,
            object_key,
            ExtraArgs={"ContentType": "application/pdf"},
        )
    except ClientError as error:
        raise HTTPException(status_code=502, detail="Unable to upload the PDF to S3.") from error

    return object_key


@router.post("/pdf")
def upload_pdf(pdf_file: UploadFile = File(...)):
    filename = os.path.basename(pdf_file.filename)
    object_key = f"uploads/{filename}"
    uploaded_key = upload_pdf_to_s3(pdf_file, object_key)
    return {"message": "PDF uploaded successfully.", "key": uploaded_key}


#@router.post("/create_account")
@router.api_route("/create_account", methods=["GET", "POST"])
async def create_account(
    request: Request,
    name: str | None = Form(default=None),
    email: str | None = Form(default=None),
    mobile: str | None = Form(default=None),
    password: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    if request.method == "POST":
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
            name = data.get("name") or name
            email = data.get("email") or email
            mobile = data.get("mobile") or mobile
            password = data.get("password") or password
        elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            form_data = await request.form()
            name = form_data.get("name") or name
            email = form_data.get("email") or email
            mobile = form_data.get("mobile") or mobile
            password = form_data.get("password") or password

    name = (name or "").strip()
    email = (email or "").strip()
    mobile = (mobile or "").strip()
    password = (password or "").strip()

    if not name or not email or not mobile or not password:
        raise HTTPException(status_code=400, detail="Name, email, mobile and password are required.")

    print("*" * 100)
    print(f"Creating account for: {name}, {email}, {mobile}")
    print("*" * 100)

    #return {"message": f"Account creation request received for {name} and {password}."}

    try:
        user_id = db.execute(
            text(
                """
                INSERT INTO user_table (
                    user_name, user_email, mobile_number, password
                )
                VALUES (
                    :user_name, :user_email, :mobile_number, :password
                )
                RETURNING user_id
                """
            ),
            {
                "user_name": name,
                "user_email": email,
                "mobile_number": mobile,
                "password": password,
            },
        ).scalar_one()
        db.commit()
        return RedirectResponse(url=f"./../static/job_prof.html?user_id={user_id}", status_code=303)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save the application.",
        ) from error


def build_job_profile_payload(data: dict) -> dict:
    """Turn all job profile form fields into a single JSON object."""
    payload = {}
    for key in [
        "designation",
        "expYears",
        "expMonths",
        "dob",
        "education",
        "achievements",
        "certifications",
        "skills",
        "profileSummary",
    ]:
        value = data.get(key)
        if value is None or value == "":
            continue
        if key in {"certifications", "skills"} and not isinstance(value, list):
            payload[key] = [value]
        else:
            payload[key] = value
    return payload


def validate_resume_pdf(resume_file: UploadFile) -> None:
    """Validate the uploaded resume before storing its metadata."""
    filename = resume_file.filename or ""
    if resume_file.content_type != "application/pdf" or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Resume must be a PDF file.")

    try:
        resume_file.file.seek(0, os.SEEK_END)
        file_size = resume_file.file.tell()
        resume_file.file.seek(0)

        if file_size > MAX_RESUME_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Resume PDF must not exceed 200 KB.")

        page_count = len(PdfReader(resume_file.file).pages)
        if page_count > MAX_RESUME_PAGES:
            raise HTTPException(status_code=400, detail="Resume PDF must not exceed 4 pages.")
    except PdfReadError as error:
        raise HTTPException(status_code=400, detail="Resume must be a valid PDF file.") from error
    finally:
        resume_file.file.seek(0)


@router.post("/complete_reg")
async def complete_reg(user_id: int,
                       request: Request, db: Session = Depends(get_db)):
    print("*"*100)
    content_type = request.headers.get("content-type", "")
    print("Content-Type:", content_type)
    resume_file = None


    file_content = None
    if "application/json" in content_type:
        data = await request.json()
        print("Received JSON data:", data)
    else:
        form_data = await request.form()
        print("Received form data:", form_data)
        data = {}
        resume_file = None
        for key, value in form_data.multi_items():

            if key == "resume": #and isinstance(value, UploadFile):
                resume_file = value
                print("Resume file detected:", resume_file.filename)
                validate_resume_pdf(resume_file)
                file_content = read_pdf(resume_file.file)
                resume_file.file.seek(0)
                continue
            clean_key = key[:-2] if key.endswith("[]") else key
            if clean_key in data:
                if not isinstance(data[clean_key], list):
                    data[clean_key] = [data[clean_key]]
                data[clean_key].append(value)
            else:
                data[clean_key] = value
    print("*"*100,"Extracted file content:", file_content,"*"*100,)
    if user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required.")

    try:
        job_profile = build_job_profile_payload(data)
        job_profile['resume_data']=file_content
        print("Job profile payload:", job_profile,type(job_profile),job_profile )
        print("json.dumps(job_profile)=", json.dumps(job_profile))
        resume_key = None
        file_id = None
        if resume_file is not None and resume_file.filename:
            file_id = f"resumes/{user_id}/{uuid4()}-{os.path.basename(resume_file.filename)}"
            try:
                resume_key = upload_pdf_to_s3(
                    resume_file,
                    file_id,
                )
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=502,
                    detail="Unable to upload the resume to S3.",
                ) from exc
        print("Resume key:", resume_key, "\n", file_id)
        embedding_input = ", ".join([f"{key}: {value}" for key, value in job_profile.items()])+", "+file_content
        insert_row(load_index(True), user_id, embedding_input, original_row=None )
        db.execute(
            text(
                """
                UPDATE user_table
                SET
                    job_profile = COALESCE(
                        CAST(:job_profile AS jsonb),
                        job_profile
                    ),
                    resume_loc = COALESCE(
                        :file_id,
                        resume_loc
                    )
                WHERE user_id = :user_id
                """
            ),
            {
                "job_profile": json.dumps(job_profile) if job_profile else None,
                "file_id": file_id,
                "user_id": user_id,
            },
        )        
        db.commit()
        save_user_index(user_id, json.dumps(job_profile))
        return {
            "message": "Application submitted successfully.",
            "user_id": int(user_id),
            "job_profile": job_profile,
            "resume_key": resume_key,
        }

    except SQLAlchemyError as error:
        print("Error occurred while saving the profile:", error)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to save the full profile.",
        ) from error


@router.post("/job_posting")
async def create_job_posting(request: Request, db: Session = Depends(get_db)):
    data = await parse_json_or_form(request)
    posting_id, details = create_job_posting_row(db, data)

    return {
        "message": "Job posting created successfully.",
        "id": posting_id,
        "details": details,
    }


@router.get("/job_postings")
def get_job_postings(db: Session = Depends(get_db)):
    """Return all active job postings with their JSONB details payload."""
    rows = db.execute(
        text(
            """
            SELECT id, details
            FROM job_posting
            WHERE is_active = TRUE
            ORDER BY id DESC
            """
        )
    ).mappings().all()

    jobs = []
    for row in rows:
        details = row["details"]
        if details is None:
            details = {}
        jobs.append({
            "id": row["id"],
            "details": details,
        })

    return jobs


@router.get("/list_users")
def list_users(
    query: str = "",
    name: str = "",
    email: str = "",
    mobile: str = "",
    db: Session = Depends(get_db),
):
    where_clause, parameters = build_user_filters(query, name, email, mobile)
    users = db.execute(
        text(
            f"""
            SELECT user_id, user_name, user_email, mobile_number, resume_loc
            FROM user_table
            {where_clause}
            ORDER BY user_id DESC
            """
        ),
        parameters,
    ).mappings().all()

    return [
        {
            "user_id": user["user_id"],
            "fullName": user["user_name"],
            "email": user["user_email"],
            "mobile": user["mobile_number"],
            "resume_key": user["resume_loc"],
            "resume_url": f"/pdf?key={user['resume_loc']}",
        }
        for user in users
    ]


@router.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.execute(
        text(
            """
            SELECT user_id, user_name, user_email, mobile_number, resume_loc
            FROM user_table
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    return {
        "user_id": user["user_id"],
        "fullName": user["user_name"],
        "email": user["user_email"],
        "mobile": user["mobile_number"],
        "resume_key": user["resume_loc"],
        "resume_url": f"/pdf?key={user['resume_loc']}",
    }


# 1. Initialize the client.
# This automatically looks for the OPENAI_API_KEY environment variable.
client = OpenAI()


def get_embedding(text: str, model: str = "text-embedding-3-small"):
    """
    Generates a vector embedding for a given text string.
    """
    text = text.replace("\n", " ")

    response = client.embeddings.create(
        input=[text],
        model=model
    )

    return response.data[0].embedding


def read_pdf(file_path) -> str:
    """
    Reads the content of a PDF file (path or file-like object) and returns it as text.
    """
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def get_embedding_from_text(text: str):
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️ Please set your OPENAI_API_KEY environment variable.")
        raise Exception("OPENAI_API_KEY not set.")

    embedding_vector = get_embedding(text)

    print(f"Text: '{text}'")
    print(f"Embedding Vector Length: {len(embedding_vector)}")
    print(f"Sample values (first 5 dimensions): {embedding_vector[:5]}")
    return embedding_vector
