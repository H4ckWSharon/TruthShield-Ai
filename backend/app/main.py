from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time
import uuid

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.core.deps import set_request_ip
from app.core.rate_limit import (
    SlidingWindowRateLimiter, extract_client_ip, build_rate_limit_response
)
from app.models.entities import User, AIModelConfig
from app.core.security import get_password_hash
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.cases import router as cases_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.fingerprints import router as fingerprints_router
from app.api.v1.reports import router as reports_router
from app.api.v1.removal import router as removal_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.admin import router as admin_router

logger = logging.getLogger("truthshield")
api_rate_limiter = SlidingWindowRateLimiter(max_requests=settings.RATE_LIMIT_RPM, window_seconds=60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Ensure at least one workspace operator/admin exists for zero-auth direct access
        existing_admin = db.query(User).filter(User.role == "admin").first()
        if not existing_admin:
            operator = User(
                id=str(uuid.uuid4()),
                email="operator@truthshield.com",
                hashed_password=get_password_hash(uuid.uuid4().hex + "!Ts2026"),
                full_name="Workspace Security Officer",
                role="admin",
                is_active=True,
                is_verified=True
            )
            db.add(operator)
            db.commit()

        model_count = db.query(AIModelConfig).count()
        if model_count == 0:
            defaults = [
                AIModelConfig(
                    model_name=settings.OLLAMA_MODEL,
                    provider="ollama",
                    is_active=settings.ENABLE_OLLAMA,
                    endpoint_url=settings.OLLAMA_BASE_URL,
                    description="Local LLM for semantic policy verification"
                ),
                AIModelConfig(
                    model_name="rule_based_heuristics",
                    provider="rule_engine",
                    is_active=True,
                    endpoint_url="internal",
                    description="Deterministic lexical, OCR, ELA, and chrominance analyzer"
                ),
                AIModelConfig(
                    model_name="perceptual_hasher_suite",
                    provider="local_vision",
                    is_active=True,
                    endpoint_url="internal",
                    description="Perceptual pHash, dHash, aHash, and RapidOCR engines"
                ),
                AIModelConfig(
                    model_name=f"faster_whisper_{settings.WHISPER_MODEL_SIZE}",
                    provider="whisper",
                    is_active=settings.ENABLE_AUDIO_TRANSCRIPTION,
                    endpoint_url="internal",
                    description="Local Faster-Whisper speech-to-text transcription"
                )
            ]
            for d in defaults:
                db.add(d)
            db.commit()
    finally:
        db.close()

    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        f"**{settings.COMPANY_NAME}** — *\"{settings.TAGLINE}\"*\n\n"
        "TruthShield AI is an enterprise-grade digital content protection, forensic multimodal "
        "investigation, perceptual content fingerprinting, and removal assistance platform."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled internal error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal security processing error occurred. Contact system administrator."}
    )

@app.middleware("http")
async def security_ratelimit_and_timing(request: Request, call_next):
    client_ip = extract_client_ip(request)
    set_request_ip(client_ip)

    # Apply sliding-window rate limiting to /api/v1 endpoints
    remaining = settings.RATE_LIMIT_RPM
    if request.url.path.startswith("/api/v1") and client_ip != "testclient":
        allowed, remaining, retry_after = api_rate_limiter.check(client_ip)
        if not allowed:
            return build_rate_limit_response(settings.RATE_LIMIT_RPM, retry_after)

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_RPM)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

api_v1_prefix = "/api/v1"
app.include_router(auth_router, prefix=api_v1_prefix)
app.include_router(dashboard_router, prefix=api_v1_prefix)
app.include_router(cases_router, prefix=api_v1_prefix)
app.include_router(evidence_router, prefix=api_v1_prefix)
app.include_router(analysis_router, prefix=api_v1_prefix)
app.include_router(fingerprints_router, prefix=api_v1_prefix)
app.include_router(reports_router, prefix=api_v1_prefix)
app.include_router(removal_router, prefix=api_v1_prefix)
app.include_router(notifications_router, prefix=api_v1_prefix)
app.include_router(admin_router, prefix=api_v1_prefix)

@app.get("/")
def root():
    return {
        "platform": settings.APP_NAME,
        "company": settings.COMPANY_NAME,
        "tagline": settings.TAGLINE,
        "version": settings.APP_VERSION,
        "auth_required": settings.REQUIRE_AUTH,
        "status": "operational",
        "documentation": "/docs"
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "platform": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "company": settings.COMPANY_NAME,
        "auth_required": settings.REQUIRE_AUTH,
    }
