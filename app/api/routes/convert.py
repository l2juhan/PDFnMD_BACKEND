import logging

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile

from app.core.config import settings
from app.core.exceptions import (
    ConversionFailedException,
    FileTooLargeException,
    InvalidFileTypeException,
    TaskNotFoundException,
)
from app.models import ConversionMode, ConvertResponse
from app.services import ConverterFactory, file_manager, task_manager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _process_conversion(task_id: str) -> None:
    """
    백그라운드 변환 처리

    Args:
        task_id: 작업 ID
    """
    try:
        task = task_manager.get_task(task_id)
    except TaskNotFoundException:
        logger.warning(f"변환 시작 실패: 작업을 찾을 수 없음 (task_id={task_id})")
        return

    try:
        # 상태 업데이트: processing
        task_manager.update_task(task_id, status="processing", progress=10)

        # 변환기 가져오기
        converter = ConverterFactory.get_converter(task.mode)

        # 변환 실행
        task_manager.update_task(task_id, progress=30)
        output_path = await converter.convert(
            input_path=task.input_path,
            output_dir=settings.OUTPUT_DIR,
            task_id=task_id,
        )

        # 완료 처리
        task_manager.update_task(
            task_id,
            status="completed",
            output_path=output_path,
            progress=100,
        )

    except Exception as e:
        # 에러 처리
        error_msg = str(e) if str(e) else "변환 중 오류가 발생했습니다"
        logger.error(f"변환 실패 (task_id={task_id}): {error_msg}")

        try:
            task_manager.update_task(task_id, error=error_msg)
        except TaskNotFoundException:
            logger.warning(
                f"에러 상태 업데이트 실패: 작업이 이미 삭제됨 (task_id={task_id})"
            )


@router.post("/convert", response_model=ConvertResponse)
async def convert_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="변환할 파일"),
    mode: ConversionMode = Form(..., description="변환 모드"),
):
    """
    파일 변환 API

    - **file**: 변환할 파일 (PDF 또는 Markdown)
    - **mode**: 변환 모드
      - `pdf-to-md`: PDF → Markdown
      - `md-to-pdf`: Markdown → PDF

    변환은 백그라운드에서 실행되며, 반환된 task_id로 상태를 조회할 수 있습니다.
    """
    # 1. 파일 확장자 검증
    expected_ext = ConverterFactory.get_accepted_extension(mode)
    filename = file.filename or "unnamed"

    if not filename.lower().endswith(expected_ext):
        raise InvalidFileTypeException(
            expected_type=expected_ext.upper().replace(".", ""),
            mode=mode,
        )

    # 2. Content-Length 헤더로 사전 크기 검증 (있는 경우)
    if file.size and file.size > settings.MAX_FILE_SIZE_BYTES:
        raise FileTooLargeException(settings.MAX_FILE_SIZE_MB)

    # 3. 파일 저장
    try:
        saved_path, file_size = await file_manager.save_upload(
            file=file.file,
            filename=filename,
            max_size=settings.MAX_FILE_SIZE_BYTES,
        )
    except FileTooLargeException:
        raise
    except Exception as e:
        raise ConversionFailedException(f"파일 저장 실패: {str(e)}")

    # 4. Task 생성
    task = task_manager.create_task(
        mode=mode,
        original_filename=filename,
        input_path=saved_path,
    )

    # 5. 백그라운드 변환 시작
    background_tasks.add_task(_process_conversion, task.task_id)

    # 6. 즉시 응답 반환
    return ConvertResponse(
        task_id=task.task_id,
        mode=mode,
        status="processing",
        message="변환이 시작되었습니다",
    )
