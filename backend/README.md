# Backend

This directory contains the initial FastAPI REST backend. It provides JWT
authentication, PostgreSQL persistence, and role- and ownership-based access
control for users, video assignments, annotations, and review decisions.

## Run locally

Start PostgreSQL and create an application database (for example,
`video_annotation`). From the repository root, install the backend, set its
connection URL and create a strong JWT secret:

```powershell
python -m pip install -e ".\backend[test]"
$env:DATABASE_URL = "postgresql://postgres:your-password@localhost:5432/video_annotation"
$env:JWT_SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:INITIAL_ADMIN_EMAIL = "admin@example.com"
$env:INITIAL_ADMIN_PASSWORD = "replace-with-a-long-unique-password"
uvicorn app.main:app --app-dir backend --reload
```

The first application startup creates the required tables in the PostgreSQL
database and creates the initial administrator if the configured email does not
exist. The database itself must already exist. Set `DATABASE_URL` to select
another PostgreSQL database.
The initial administrator variables are optional, but must be provided
together. Existing administrator passwords are never reset by bootstrap.

Interactive API documentation is available at `/docs`. Authenticate by posting
JSON credentials to `POST /api/auth/login`, then send the returned bearer token
in the `Authorization` header.

## Initial routes

- `POST /api/auth/login` and `GET /api/auth/me`
- Administrator-only user creation, listing, role changes, and deletion at
  `/api/users`
- Authenticated `POST /api/videos/upload` for MP4 and MOV uploads. Source bytes
  are stored unchanged under `storage/videos/original` by default; duplicate
  filenames return `409` and are never overwritten.
- Administrator-only video creation and assignment; users can list only
  videos assigned to them
- Annotation creation/editing by annotators, review decisions/comments by
  reviewers, and administrator-wide annotation access

Video uploads are limited to 500 MiB by default. Set `MAX_VIDEO_SIZE_MB` to
change the limit and `VIDEO_STORAGE_PATH` to change the source-video directory.
The host must provide `ffprobe` on `PATH` for initial duration, resolution,
frame-rate, and codec extraction. Successful uploads are handed to a FastAPI
background task and advance to `PROCESSING`; the multimodal processing
implementation can be connected at `app/services/video_processing.py`.

Existing SQLite data is not automatically copied to PostgreSQL. Back up or
export any data you need before switching database backends.

Passwords are stored using Argon2id. Access tokens are signed with HS256 and
expire after 30 minutes by default; use `ACCESS_TOKEN_MINUTES` to override the
duration. The token signing key is required and must be at least 32 characters.
