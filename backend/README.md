# Backend

This directory contains the initial FastAPI REST backend. It provides JWT
authentication, SQLite persistence, and role- and ownership-based access
control for users, video assignments, annotations, and review decisions.

## Run locally

From the repository root, install the backend and create a strong JWT secret:

```powershell
python -m pip install -e ".\backend[test]"
$env:JWT_SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:INITIAL_ADMIN_EMAIL = "admin@example.com"
$env:INITIAL_ADMIN_PASSWORD = "replace-with-a-long-unique-password"
uvicorn app.main:app --app-dir backend --reload
```

The first application startup creates the SQLite database at
`backend/data/app.sqlite3` and creates the initial administrator if the
configured email does not exist. Set `DATABASE_PATH` to use another location.
The initial administrator variables are optional, but must be provided
together. Existing administrator passwords are never reset by bootstrap.

Interactive API documentation is available at `/docs`. Authenticate by posting
JSON credentials to `POST /api/auth/login`, then send the returned bearer token
in the `Authorization` header.

## Initial routes

- `POST /api/auth/login` and `GET /api/auth/me`
- Administrator-only user creation, listing, role changes, and deletion at
  `/api/users`
- Administrator-only video creation and assignment; users can list only
  videos assigned to them
- Annotation creation/editing by annotators, review decisions/comments by
  reviewers, and administrator-wide annotation access

Passwords are stored using Argon2id. Access tokens are signed with HS256 and
expire after 30 minutes by default; use `ACCESS_TOKEN_MINUTES` to override the
duration. The token signing key is required and must be at least 32 characters.
