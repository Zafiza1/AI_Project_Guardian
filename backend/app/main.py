from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database.database import SessionLocal, init_db
from app.routes.diagnosis import router as diagnosis_router
from app.routes.projects import router as projects_router
from app.routes.system import router as system_router
from app.services import diagnosis_service, health_check_service


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as db:
        health_check_service.mark_interrupted_checks(db)
    yield
    health_check_service.shutdown()
    diagnosis_service.shutdown()


app = FastAPI(title="AI Project Guardian API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(projects_router)
app.include_router(system_router)
app.include_router(diagnosis_router)


@app.get("/")
def root():
    return {"message": "AI Project Guardian API", "version": app.version, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}
