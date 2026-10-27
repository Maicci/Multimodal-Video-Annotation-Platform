# Local setup

The initial REST backend lives in `backend/`. From the repository root, install
it and configure its signing key and initial administrator:

```powershell
python -m pip install -e ".\backend[test]"
$env:JWT_SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:INITIAL_ADMIN_EMAIL = "admin@example.com"
$env:INITIAL_ADMIN_PASSWORD = "replace-with-a-long-unique-password"
uvicorn app.main:app --app-dir backend --reload
```


The prototype under `examples/` remains available independently:
`python -m pip install -e ./examples/backend`, then
`uvicorn examples.backend.app.main:app --reload`.
