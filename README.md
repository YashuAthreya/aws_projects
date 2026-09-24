# CareerHub / AWS Job Board Platform

A full-stack AI-powered hiring platform built with FastAPI, PostgreSQL, OpenAI embeddings, FAISS, and AWS S3. The project lets candidates create profiles, upload resumes, and be matched to jobs semantically. Recruiters can publish job openings, filter candidates, and search the talent pool using structured and natural-language queries.

This repository is a practical example of a modern applicant-tracking and hiring workflow: job postings are stored as JSONB documents, profile/resume text is embedded into vectors, and similarity search is used to surface relevant jobs and candidates.

---

## Business Problem Solved

Hiring teams often struggle to find the right candidate among large pools of resumes and applications. Traditional keyword-only matching misses context, synonyms, and role similarity. This project addresses that by blending:

- structured profile data from candidates
- PDF resume parsing
- AI-based embeddings for semantic understanding
- FAISS vector indexing for fast similarity search
- recruiter-friendly listing and filtering pages

The result is a job board + matching system that can rank jobs and candidates by relevance, not just exact keyword overlap.

---

## Core Features

### Candidate-side features
- User registration with name, email, mobile, and password
- Job profile completion with designation, experience, education, achievements, skills, certifications, and summary
- Resume upload in PDF format
- Resume validation for file type, file size, and page count
- AI-based embedding generation from user profile + resume content
- Semantic search for jobs that match a candidate profile

### Recruiter/admin-side features
- Job posting creation in a structured form
- Job listing with JSONB payload storage
- Candidate listing and filtering by name, email, and mobile
- Resume retrieval from S3
- Semantic job search using natural-language input
- Profile similarity scoring between candidate and job postings

### Platform features
- FastAPI REST API and HTML render routes
- PostgreSQL persistence via SQLAlchemy
- PostgreSQL JSONB support for flexible job and profile payloads
- FAISS indexes for semantic matching
- AWS S3 storage for uploaded resumes
- Session management for authenticated flows
- Health endpoint and app startup initialization

---

## Architecture Overview

```text
Browser / Frontend
    │
    ▼
FastAPI app
    │
    ├── Auth routes (/auth/*)
    ├── User routes (/create_account, /complete_reg, /list_users, /jobs/*)
    ├── Admin routes (/admin/*)
    ├── Static HTML pages (/static/*)
    │
    ├── PostgreSQL (SQLAlchemy)
    │       ├── user_table
    │       ├── job_posting
    │       └── user_sessions
    │
    ├── AWS S3
    │       └── uploaded resume PDFs
    │
    ├── OpenAI Embeddings API
    │       └── text-embedding-3-small
    │
    └── FAISS indexes
            ├── user_faiss.index
            └── admin_faiss.index
```

This architecture separates storage of relational data from vector search and file storage, which is a common pattern for AI-powered hiring systems.

---

## Project Structure

```text
aws_projects/
├── README.md
├── requirements.txt
├── download_youtube.py
├── src/
│   ├── app/
│   │   ├── admin/
│   │   │   ├── __init__.py
│   │   │   ├── auth_router.py
│   │   │   ├── auth_service.py
│   │   │   ├── dependencies.py
│   │   │   ├── models.py
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   └── security.py
│   │   ├── auth/
│   │   │   ├── auth_service.py
│   │   │   ├── dependencies.py
│   │   │   ├── router.py
│   │   │   └── security.py
│   │   ├── database.py
│   │   ├── faiss_view.py
│   │   ├── index_gen.py
│   │   ├── job_service.py
│   │   ├── log_service.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── request_utils.py
│   │   ├── schemas.py
│   │   ├── user_router.py
│   │   └── user_service.py
│   ├── data/
│   │   ├── admin_faiss.index
│   │   └── user_faiss.index
│   └── static/
│       ├── admin_dashboard.html
│       ├── admin_job_posting_form.html
│       ├── admin_job_postings.html
│       ├── admin_signin.html
│       ├── admin_users.html
│       ├── embeddings_view.html
│       ├── get_resume.html
│       ├── index.html
│       ├── job_posting.html
│       ├── job_postings_list.html
│       ├── job_prof.html
│       ├── list_users.html
│       ├── signin.html
│       ├── user_detail.html
│       ├── user_reg.html
│       └── admin_*.html
└──
```

### Important project modules
- `src/app/main.py`: app entry point and router mounting
- `src/app/database.py`: SQLAlchemy engine and DB session creation
- `src/app/models.py`: ORM models for users, sessions, and postings
- `src/app/index_gen.py`: FAISS indexing and embedding utilities
- `src/app/job_service.py`: job posting validation and creation logic
- `src/app/user_router.py`: public candidate flows and resume handling
- `src/app/admin/router.py`: admin-specific endpoints
- `src/app/auth/*.py`: login, register, cookie/session behavior

---

## Data Model Details

### `user_table`
Stores a candidate's core identity and profile information.

| Column | Type | Notes |
|---|---|---|
| `user_id` | SERIAL PK | Generated user id |
| `user_name` | TEXT | Candidate name |
| `user_email` | TEXT | Candidate email |
| `mobile_number` | TEXT | Candidate phone number |
| `password` | TEXT | Password or hashed value |
| `job_profile` | JSONB | Structured profile data |
| `resume_loc` | TEXT | S3 key for uploaded PDF |
| `is_active` | BOOLEAN | Status flag |
| `created_at` | TIMESTAMPTZ | Row creation time |
| `updated_at` | TIMESTAMPTZ | Update timestamp |
| `last_login_at` | TIMESTAMPTZ | Most recent login |

### `job_posting`
Stores recruiter-created job posts as JSON documents.

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | Job posting id |
| `details` | JSONB | Job properties such as title, skills, location, experience |
| `is_active` | BOOLEAN | Controls visibility to public job listings |
| `emb_generated` | BOOLEAN | Tracks whether posting was indexed for embedding search |

### `user_sessions`
Tracks authenticated sessions for user identity and admin flows.

| Column | Type | Notes |
|---|---|---|
| `session_id` | SERIAL PK | Session record id |
| `user_id` | INTEGER | Linked user |
| `session_token_hash` | TEXT | Hashed token |
| `created_at` | TIMESTAMPTZ | Session start |
| `expires_at` | TIMESTAMPTZ | Expiration date |
| `last_used_at` | TIMESTAMPTZ | Last activity |
| `revoked_at` | TIMESTAMPTZ | Logout or invalidation |
| `ip_address` | TEXT | Client IP |
| `user_agent` | TEXT | Browser/user-agent string |

---

## Database Initialization

The app expects PostgreSQL tables to exist before requests hit the database.

### SQL used by the project

```sql
CREATE TABLE user_table (
    user_id       SERIAL PRIMARY KEY,
    user_name     TEXT,
    user_email    TEXT,
    mobile_number TEXT,
    password      TEXT,
    job_profile   JSONB,
    resume_loc    TEXT,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE TABLE job_posting (
    id            SERIAL PRIMARY KEY,
    details       JSONB,
    is_active     BOOLEAN DEFAULT TRUE,
    emb_generated BOOLEAN DEFAULT FALSE
);

CREATE TABLE user_sessions (
    session_id         SERIAL PRIMARY KEY,
    user_id            INTEGER,
    session_token_hash TEXT,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    expires_at         TIMESTAMPTZ,
    last_used_at       TIMESTAMPTZ DEFAULT NOW(),
    revoked_at         TIMESTAMPTZ,
    ip_address         TEXT,
    user_agent         TEXT
);
```

---

## Required Environment Variables

Create a `.env` file in the project root and configure these values.

```bash
DATABASE_URL=postgresql+psycopg://postgres:yourpassword@localhost:5432/yourdb
S3_BUCKET=your-s3-bucket-name
OPENAI_API_KEY=sk-...
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1
```

### Variable descriptions

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string used by SQLAlchemy |
| `S3_BUCKET` | Yes | AWS bucket for resume uploads |
| `OPENAI_API_KEY` | Yes | API key for embedding generation |
| `AWS_ACCESS_KEY_ID` | Yes | AWS credentials for S3 |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS secret key |
| `AWS_DEFAULT_REGION` | No | AWS region; defaults to us-east-1 when unset |

> Keep secrets out of Git. Add `.env` to `.gitignore`.

---

## Setup and Installation

### Prerequisites

- Python 3.11+
- PostgreSQL database running locally or remotely
- AWS account with S3 bucket configured
- OpenAI API key
- Optional: pgAdmin or another DB visual tool

### 1. Clone the repository

```bash
git clone <repo-url>
cd aws_projects
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

On Windows:

```powershell
venv\Scripts\activate
```

On macOS/Linux:

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create `.env` at the project root with the variables listed above.

### 5. Initialize database tables

Make sure PostgreSQL contains the required tables before starting the app.

### 6. Start the app

From the repo root:

```bash
uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open:

- http://localhost:8000/
- http://localhost:8000/docs
- http://localhost:8000/redoc
- http://localhost:8000/health

---

## Resume Handling and Validation

Resume uploads are validated before they are saved or sent to S3.

### Rules enforced
- only PDF files are allowed
- maximum size is 200 KB
- maximum pages is 4

### Validation logic
The code checks:
- `resume_file.content_type == "application/pdf"`
- file extension ends with `.pdf`
- file size is under `MAX_RESUME_SIZE_BYTES`
- PDF page count is under `MAX_RESUME_PAGES`

If validation fails, the API raises an HTTP 400 error before writing any data.

---

## How AI Matching Works

The system uses a combination of structured profile data and resume text to produce embeddings.

### Flow
1. Candidate completes profile form.
2. Resume PDF is parsed to text.
3. The application combines profile fields and resume text into one string.
4. OpenAI embedding API converts the text into a vector.
5. The vector is inserted into a FAISS index for similarity search.
6. Recruiters or users can search using a natural-language query.
7. FAISS returns nearest neighbors ranked by similarity.

### Related functions
- `get_embedding()` in `src/app/user_router.py`
- `insert_row()` and `search()` in `src/app/index_gen.py`
- `compute_job_match_scores()` for job-to-user scoring

---

## Job Search and Candidate Search

### Public job listing
The landing page reads active job postings from the DB and renders them to HTML.

### Structured filters
Several query parameters are supported, such as:
- `name`
- `email`
- `mobile`
- `query`

### Semantic search
The app supports natural-language queries for both:
- candidate discovery
- job discovery by similarity matching

This provides a richer search experience than plain SQL `LIKE` matching.

---

## Authentication and Session Flow

The app stores user sessions and checks them via dependencies.

Typical flow:
1. User submits registration form.
2. User account is inserted into `user_table`.
3. User logs in.
4. A session token is created and stored in the DB.
5. Protected routes use auth dependencies to ensure a valid session.

Session-related models and logic live under:
- `src/app/auth/`
- `src/app/models.py`
- `src/app/log_service.py`

---

## AWS S3 Integration

Resumes are uploaded to S3 using `boto3` and stored under a structured key such as:

```text
resumes/{user_id}/{uuid4()}-{filename}.pdf
```

The project also exposes endpoints to retrieve a document by key:

```text
GET /pdf?key=<object-key>
```

This is useful for previewing or downloading resumes through the browser.

---

## Admin Features

The admin area is handled in `src/app/admin/` and includes routes for:
- admin login / authentication
- admin dashboard
- job posting forms
- job posting management
- candidate review
- indexing jobs and users into vector search vectors

These are separate from the public candidate-facing endpoints.

---

## Common Troubleshooting

### 1. `UndefinedTable: relation "job_posting" does not exist`
This means the PostgreSQL database you are connected to does not have the `job_posting` table.

Fix:
- confirm `DATABASE_URL` points to the correct DB
- create the required tables manually or run schema initialization
- verify the database is actually running

### 2. Missing AWS credentials or S3 bucket
If uploads fail, check:
- `S3_BUCKET`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION`

### 3. `OPENAI_API_KEY not set`
Embedding generation requires a valid OpenAI key. Set it in `.env` before using semantic-search features.

### 4. `pgAdmin` port conflict
If pgAdmin cannot start because port `5050` is in use, stop stale pgAdmin processes or free the port before restarting.

---

## Production Considerations

This repository is a working prototype and can be improved further with:
- Alembic migrations instead of raw SQL schema creation
- production-grade auth and password hashing policy
- private S3 bucket policies and IAM roles
- background job processing for embeddings generation
- Redis or Celery for background indexing tasks
- proper CI/CD and environment separation
- secret management via AWS Secrets Manager or environment injection

---

## Summary

This project is a candidate-driven hiring platform with:
- structured user profiles
- PDF resume upload
- semantic search and matching powered by OpenAI + FAISS
- recruiter job posting management
- PostgreSQL and AWS S3 integration

It is a good reference for building an AI-aided recruitment or talent-matching solution with a full-stack Python app.

---

## License

This repository does not currently include a license file. If you intend to share or distribute it publicly, add an explicit license such as MIT or Apache 2.0.

