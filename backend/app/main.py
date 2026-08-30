from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.query import router as query_router
from app.api.retrieval import router as retrieval_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Finance RAG system — Phase 4 (RAG generation with citations).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(documents_router, prefix=settings.API_V1_PREFIX)
app.include_router(retrieval_router, prefix=settings.API_V1_PREFIX)
app.include_router(query_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root() -> dict:
    return {"message": f"{settings.APP_NAME} API — see {settings.API_V1_PREFIX}/health"}
