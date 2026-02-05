import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import content, convert, download, status
from app.core.config import settings
from app.core.exceptions import PDFnMDException
from app.services import task_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작시 실행
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 만료 작업 정리 스케줄러 시작
    await task_manager.start_cleanup_scheduler(interval_minutes=10)

    yield

    # 종료시 실행
    task_manager.stop_cleanup_scheduler()


app = FastAPI(
    title="PDFnMD",
    description="PDF ↔ Markdown 양방향 변환 서비스",
    version="0.1.0",
    lifespan=lifespan,
    # 프로덕션에서는 docs/openapi 비활성화
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
)


# =============================================================================
# 미들웨어 설정
# =============================================================================

# CORS 미들웨어 (보안 강화)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],  # 필요한 메서드만
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Content-Disposition"],
    max_age=600,  # preflight 캐시 10분
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """보안 헤더 추가 미들웨어"""
    # Request ID 생성/전달
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    response = await call_next(request)

    # 보안 헤더 추가
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # 프로덕션에서 추가 보안 헤더
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    return response


# =============================================================================
# 에러 핸들러
# =============================================================================

@app.exception_handler(PDFnMDException)
async def pdfnmd_exception_handler(request: Request, exc: PDFnMDException):
    """커스텀 예외 핸들러"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={"X-Request-ID": request.headers.get("X-Request-ID", "")},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """일반 예외 핸들러 (프로덕션에서 상세 에러 숨김)"""
    if settings.is_development:
        detail = str(exc)
    else:
        detail = "서버 오류가 발생했습니다"

    return JSONResponse(
        status_code=500,
        content={"detail": detail},
        headers={"X-Request-ID": request.headers.get("X-Request-ID", "")},
    )


# =============================================================================
# 엔드포인트
# =============================================================================

@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy"}


# API 라우터 등록
app.include_router(convert.router, prefix="/api", tags=["convert"])
app.include_router(status.router, prefix="/api", tags=["status"])
app.include_router(download.router, prefix="/api", tags=["download"])
app.include_router(content.router, prefix="/api", tags=["content"])
