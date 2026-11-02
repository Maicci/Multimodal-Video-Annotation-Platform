# Testing

Run backend tests from the repository root with
`python -m pytest backend/tests`. The backend tests require `TEST_DATABASE_URL`
to point to a PostgreSQL test database; each test uses a disposable schema.
Frontend, processing, and end-to-end test suites will be added alongside their
implementations.
