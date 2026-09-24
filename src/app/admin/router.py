# app/admin/router.py

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.admin.dependencies import get_current_admin
from app.admin.models import Admin
from app.database import get_db
from app.index_gen import (
    get_job_embedding_records,
    get_user_embedding_records,
    index_job_postings,
    index_pending_users,
    load_index,
)
from app.job_service import create_job_posting_row, update_job_posting_row
from app.request_utils import parse_json_or_form
from app.user_service import build_user_filters
from sqlalchemy import text


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


@router.get("/")
def admin_root_page():
    return RedirectResponse(url="./../static/admin_signin.html")


@router.get("/dashboard")
def admin_dashboard_page():
    return RedirectResponse(url="./../static/admin_dashboard.html")


@router.get("/users")
def admin_list_users(
    query: str = "",
    name: str = "",
    email: str = "",
    mobile: str = "",
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # Reuses the same query builder as the public /list_users endpoint,
    # then joins with FAISS so the admin can see embedding status too.
    where_clause, parameters = build_user_filters(query, name, email, mobile)

    if where_clause or query or name or email or mobile:
        rows = db.execute(
            text(
                f"""
                SELECT user_id
                FROM user_table
                {where_clause}
                ORDER BY user_id DESC
                """
            ),
            parameters,
        ).mappings().all()
        allowed_ids = {row["user_id"] for row in rows}
        return [
            record for record in get_user_embedding_records(db)
            if record["user_id"] in allowed_ids
        ]

    return get_user_embedding_records(db)


@router.get("/job_postings")
def admin_list_job_postings(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # Includes inactive postings and embedding status, unlike the public /job_postings endpoint.
    return get_job_embedding_records(db)


@router.post("/job_postings", status_code=201)
async def admin_create_job_posting(
    request: Request,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    data = await parse_json_or_form(request)
    posting_id, details = create_job_posting_row(db, data)

    return {
        "message": "Job posting created successfully.",
        "id": posting_id,
        "details": details,
    }


@router.put("/job_postings/{job_id}")
async def admin_update_job_posting(
    job_id: int,
    request: Request,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    data = await parse_json_or_form(request)
    is_active = data.pop("is_active", None)
    if isinstance(is_active, str):
        is_active = is_active.strip().lower() in {"true", "1", "yes", "on"}

    updated_details = update_job_posting_row(db, job_id, data, is_active=is_active)

    if updated_details is None:
        raise HTTPException(status_code=404, detail="Job posting not found.")

    return {
        "message": "Job posting updated successfully.",
        "id": job_id,
        "details": updated_details,
    }


@router.post("/embeddings/generate")
def admin_generate_embeddings(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # Only embeds rows that don't already have a stored vector.
    users_indexed = index_pending_users(db, load_index(True))
    jobs_indexed = index_job_postings(db, load_index(False), only_pending=True)

    return {
        "message": "Embedding generation complete.",
        "users_indexed": users_indexed,
        "job_postings_indexed": jobs_indexed,
    }
