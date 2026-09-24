# app/job_service.py

import json

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


def normalize_job_posting(details: dict) -> dict:
    """Convert DB JSON payload to the shape expected by the landing page."""
    if not isinstance(details, dict):
        return {}

    normalized = dict(details)

    mandatory = normalized.get("mandatorySkills", [])
    optional = normalized.get("optionalSkills", [])

    if isinstance(mandatory, str):
        mandatory = [item.strip() for item in mandatory.split(",") if item.strip()]
    elif mandatory is None:
        mandatory = []
    elif not isinstance(mandatory, list):
        mandatory = [mandatory]

    if isinstance(optional, str):
        optional = [item.strip() for item in optional.split(",") if item.strip()]
    elif optional is None:
        optional = []
    elif not isinstance(optional, list):
        optional = [optional]

    normalized["mandatorySkills"] = mandatory
    normalized["optionalSkills"] = optional

    if "experience" not in normalized and ("expMin" in normalized or "expMax" in normalized):
        exp_min = normalized.get("expMin")
        exp_max = normalized.get("expMax")
        if exp_min is not None and exp_max is not None:
            normalized["experience"] = f"{exp_min}-{exp_max} years"
        elif exp_min is not None:
            normalized["experience"] = f"{exp_min}+ years"
        elif exp_max is not None:
            normalized["experience"] = f"Up to {exp_max} years"

    if "posted" not in normalized:
        normalized["posted"] = "Recently"

    return normalized


def build_job_posting_payload(data: dict) -> dict:
    """Normalize every job posting form field into a single JSON object."""
    payload = {}
    list_fields = {"mandatorySkills", "optionalSkills"}
    number_fields = {"expMin", "expMax"}

    for key, value in data.items():
        if key in number_fields:
            if value in (None, ""):
                payload[key] = None
                continue
            try:
                payload[key] = int(value)
            except (TypeError, ValueError):
                payload[key] = value
            continue

        if key in list_fields:
            if isinstance(value, list):
                items = value
            elif value in (None, ""):
                items = []
            else:
                items = str(value).split(",")
            payload[key] = [str(item).strip() for item in items if str(item).strip()]
            continue

        payload[key] = value.strip() if isinstance(value, str) else value

    return payload


def create_job_posting_row(db: Session, data: dict) -> tuple[int, dict]:
    """Validate and insert a new job posting. Returns (id, normalized_details)."""
    if not isinstance(data, dict) or not data:
        raise HTTPException(status_code=400, detail="Job posting details are required.")

    details = build_job_posting_payload(data)

    try:
        posting_id = db.execute(
            text(
                """
                INSERT INTO job_posting (details, is_active, emb_generated)
                VALUES (CAST(:details AS jsonb), TRUE, FALSE)
                RETURNING id
                """
            ),
            {"details": json.dumps(details)},
        ).scalar_one()
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to save the job posting.") from error

    return posting_id, details


def update_job_posting_row(
    db: Session,
    job_id: int,
    data: dict,
    is_active: bool | None = None,
) -> dict | None:
    """Merge new fields into an existing job posting. Returns merged details, or None if not found."""
    row = db.execute(
        text("SELECT id, details FROM job_posting WHERE id = :id"),
        {"id": job_id},
    ).mappings().one_or_none()

    if row is None:
        return None

    existing_details = row["details"] or {}
    if isinstance(existing_details, str):
        existing_details = json.loads(existing_details)

    incoming_details = build_job_posting_payload(data) if data else {}
    merged_details = {**existing_details, **incoming_details}

    set_clauses = ["details = CAST(:details AS jsonb)"]
    params = {"id": job_id, "details": json.dumps(merged_details)}

    # Content changed -> the existing embedding is now stale, flag it for regeneration.
    if incoming_details:
        set_clauses.append("emb_generated = FALSE")

    if is_active is not None:
        set_clauses.append("is_active = :is_active")
        params["is_active"] = bool(is_active)

    try:
        db.execute(
            text(f"UPDATE job_posting SET {', '.join(set_clauses)} WHERE id = :id"),
            params,
        )
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to update the job posting.") from error

    return merged_details
