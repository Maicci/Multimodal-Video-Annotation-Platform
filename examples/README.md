# Example application

This directory contains the runnable prototype, kept separate from the
`backend` and `frontend` starter skeletons.

From the repository root, install and launch the example backend with:

```bash
python -m pip install -e ./examples/backend
uvicorn examples.backend.app.main:app --reload
```

The FastAPI app serves the example browser UI at http://127.0.0.1:8000.
