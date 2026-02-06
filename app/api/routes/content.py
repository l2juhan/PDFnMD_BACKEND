from fastapi import APIRouter

from app.core.exceptions import ConversionFailedException
from app.models.response import ContentResponse
from app.services import task_manager

router = APIRouter()


@router.get("/content/{task_id}", response_model=ContentResponse)
async def get_content(task_id: str):
    """
    변환된 마크다운 텍스트 조회

    - **task_id**: 변환 작업 ID

    완료된 PDF→MD 작업의 마크다운 텍스트를 반환합니다.
    다운로드 없이 텍스트를 복사하여 사용할 수 있습니다.
    """
    task = task_manager.get_task(task_id)

    # 작업 상태 확인
    if task.status == "pending":
        raise ConversionFailedException("변환이 아직 시작되지 않았습니다")
    if task.status == "processing":
        raise ConversionFailedException("변환이 진행 중입니다. 잠시 후 다시 시도해주세요")
    if task.status == "failed":
        raise ConversionFailedException(f"변환에 실패했습니다: {task.error or '알 수 없는 오류'}")

    # 출력 파일 확인
    if not task.output_path or not task.output_path.exists():
        raise ConversionFailedException("결과 파일을 찾을 수 없습니다")

    # 마크다운 파일만 지원
    if task.output_path.suffix.lower() != ".md":
        raise ConversionFailedException(
            "PDF 파일은 텍스트 조회를 지원하지 않습니다. 다운로드 API를 사용해주세요"
        )

    # 파일 내용 읽기 (UTF-8)
    content = task.output_path.read_text(encoding="utf-8")

    # 콘텐츠 크기 계산
    content_bytes = content.encode("utf-8")
    size_bytes = len(content_bytes)
    size_kb = round(size_bytes / 1024, 2)

    return ContentResponse(
        task_id=task_id,
        content=content,
        format="gfm",
        original_filename=task.original_filename,
        size_bytes=size_bytes,
        size_kb=size_kb,
    )
