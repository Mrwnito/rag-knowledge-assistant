
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router

from app.db.init_db import init_db

app = FastAPI(title="RAG Knowledge Assistant API")

# Autorise le frontend à appeler l'API (dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
app.include_router(api_router)
@app.on_event("startup")
def on_startup() -> None:
    init_db()


