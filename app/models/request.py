from typing import List

from pydantic import BaseModel, Field


class BatchDownloadRequest(BaseModel):
    """다중 파일 다운로드 요청"""

    task_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="다운로드할 작업 ID 목록",
    )
