# Local setup

The initial REST backend lives in `backend/` and requires a running PostgreSQL
server and an already-created application database. From the repository root,
install it and configure its database URL, signing key, and initial
administrator:

```powershell
python -m pip install -e ".\backend[test]"
$env:DATABASE_URL = "postgresql://postgres:your-password@localhost:5432/video_annotation"
$env:JWT_SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:INITIAL_ADMIN_EMAIL = "admin@example.com"
$env:INITIAL_ADMIN_PASSWORD = "replace-with-a-long-unique-password"
uvicorn app.main:app --app-dir backend --reload
```

For backend tests, point `TEST_DATABASE_URL` at a separate PostgreSQL test
database; each test creates and removes an isolated schema:

```powershell
$env:TEST_DATABASE_URL = "postgresql://postgres:your-password@localhost:5432/video_annotation_test"
python -m pytest backend/tests
```


The prototype under `examples/` remains available independently:
`python -m pip install -e ./examples/backend`, then
`uvicorn examples.backend.app.main:app --reload`.
