from pydantic import BaseModel, Field

from app.models.types import ConversionMode, TaskStatus


class ConvertResponse(BaseModel):
    """변환 시작 응답"""

    task_id: str = Field(..., description="작업 ID")
    mode: ConversionMode = Field(..., description="변환 모드")
    status: TaskStatus = Field(default="processing", description="작업 상태")
    message: str = Field(default="변환이 시작되었습니다", description="상태 메시지")


class StatusResponse(BaseModel):
    """작업 상태 조회 응답"""

    task_id: str = Field(..., description="작업 ID")
    mode: ConversionMode = Field(..., description="변환 모드")
    status: TaskStatus = Field(..., description="작업 상태")
    progress: int = Field(default=0, ge=0, le=100, description="진행률 (%)")
    download_url: str | None = Field(default=None, description="다운로드 URL")
    error: str | None = Field(default=None, description="에러 메시지")
    filename: str | None = Field(default=None, description="원본 파일명")


class HealthResponse(BaseModel):
    """헬스 체크 응답"""

    status: str = Field(default="healthy", description="서버 상태")
