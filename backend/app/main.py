from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.videoplayer import router as videos_router


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    videos_router,
    prefix="/api",
)


@app.get("/")
def root():
    return {"message": "Backend is running"}
