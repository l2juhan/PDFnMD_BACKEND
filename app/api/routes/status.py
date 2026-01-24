from fastapi import APIRouter

from app.models import StatusResponse
from app.services import task_manager

router = APIRouter()


@router.get("/status/{task_id}", response_model=StatusResponse)
async def get_task_status(task_id: str):
    """
    변환 작업 상태 조회

    - **task_id**: 변환 요청시 반환된 작업 ID

    반환값:
    - `status`: pending, processing, completed, failed
    - `progress`: 0-100 (진행률)
    - `download_url`: 완료시 다운로드 URL
    - `error`: 실패시 에러 메시지
    """
    task = task_manager.get_task(task_id)

    return StatusResponse(
        task_id=task.task_id,
        mode=task.mode,
        status=task.status,
        progress=task.progress,
        download_url=task.download_url,
        error=task.error,
        filename=task.original_filename,
    )
