from functools import lru_cache
from pathlib import Path
from typing import List, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """PDFnMD 애플리케이션 설정"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # 서버
    ENV: Literal["development", "production", "testing"] = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5174"]

    # 파일 제한
    MAX_FILE_SIZE_MB: int = 20

    # 경로
    UPLOAD_DIR: Path = Path("./uploads")
    OUTPUT_DIR: Path = Path("./outputs")

    # 파일 보관 시간
    FILE_RETENTION_HOURS: int = 24

    # Cloudflare R2 (이미지 영구 저장)
    R2_ACCESS_KEY_ID: str | None = None
    R2_SECRET_ACCESS_KEY: str | None = None
    R2_BUCKET_NAME: str | None = None
    R2_ENDPOINT_URL: str | None = None  # 필수: https://<ACCOUNT_ID>.r2.cloudflarestorage.com
    R2_PUBLIC_URL: str | None = None  # 퍼블릭 URL: https://pub-xxx.r2.dev

    # marker (PDF → MD)
    MARKER_USE_GPU: bool = False

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """문자열 CORS origins을 리스트로 파싱"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        """파일당 최대 크기 (bytes)"""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def is_development(self) -> bool:
        """개발 환경 여부"""
        return self.ENV == "development"

    @property
    def is_production(self) -> bool:
        """프로덕션 환경 여부"""
        return self.ENV == "production"

    @property
    def is_r2_enabled(self) -> bool:
        """R2 활성화 여부 (4개 필수값 모두 필요)"""
        return all([
            self.R2_ACCESS_KEY_ID,
            self.R2_SECRET_ACCESS_KEY,
            self.R2_BUCKET_NAME,
            self.R2_ENDPOINT_URL,
        ])

    def ensure_directories(self) -> None:
        """업로드/출력 디렉토리 생성"""
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """설정 싱글톤 반환 (캐싱)"""
    return Settings()


# 기본 설정 인스턴스 (get_settings()와 동일 인스턴스 사용)
settings = get_settings()
