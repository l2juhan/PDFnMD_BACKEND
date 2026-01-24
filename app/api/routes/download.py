from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from app.core.exceptions import ConversionFailedException, TaskNotFoundException
from app.models import BatchDownloadRequest
from app.services import file_manager, task_manager

router = APIRouter()


def _get_content_disposition(filename: str, mode: str) -> str:
    """Content-Disposition 헤더 생성 (한글 파일명 지원)"""
    # RFC 5987 인코딩
    encoded_filename = quote(filename)
    return f"attachment; filename*=UTF-8''{encoded_filename}"


@router.get("/download/{task_id}")
async def download_file(task_id: str):
    """
    변환된 파일 다운로드 (단일)

    - **task_id**: 변환 작업 ID

    완료된 작업의 결과 파일을 다운로드합니다.
    """
    task = task_manager.get_task(task_id)

    # 완료 상태 확인
    if task.status != "completed":
        if task.status == "failed":
            raise ConversionFailedException(task.error or "변환에 실패했습니다")
        raise ConversionFailedException(
            f"변환이 아직 완료되지 않았습니다 (상태: {task.status})"
        )

    # 출력 파일 확인
    if not task.output_path or not task.output_path.exists():
        raise ConversionFailedException("변환 결과 파일을 찾을 수 없습니다")

    # 다운로드 파일명 생성
    original_stem = task.original_filename.rsplit(".", 1)[0]
    output_ext = task.output_path.suffix
    download_filename = f"{original_stem}{output_ext}"

    # Content-Type 결정
    if output_ext == ".md":
        media_type = "text/markdown; charset=utf-8"
    elif output_ext == ".pdf":
        media_type = "application/pdf"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=task.output_path,
        filename=download_filename,
        media_type=media_type,
        headers={
            "Content-Disposition": _get_content_disposition(download_filename, "attachment")
        },
    )


@router.post("/download/batch")
async def download_batch(request: BatchDownloadRequest):
    """
    여러 변환 결과 파일 ZIP 다운로드

    - **task_ids**: 다운로드할 작업 ID 목록

    완료된 모든 작업의 결과를 ZIP으로 압축하여 다운로드합니다.
    """
    files_to_zip = []
    errors = []

    for task_id in request.task_ids:
        try:
            task = task_manager.get_task(task_id)

            if task.status != "completed":
                errors.append(f"{task_id[:8]}: 완료되지 않음")
                continue

            if not task.output_path or not task.output_path.exists():
                errors.append(f"{task_id[:8]}: 파일 없음")
                continue

            files_to_zip.append(task.output_path)

        except TaskNotFoundException:
            errors.append(f"{task_id[:8]}: 작업을 찾을 수 없음")

    # 다운로드할 파일이 없으면 에러
    if not files_to_zip:
        error_detail = "; ".join(errors) if errors else "다운로드할 파일이 없습니다"
        raise ConversionFailedException(error_detail)

    # ZIP 생성 (메모리 내)
    zip_bytes = file_manager.create_zip_bytes(files_to_zip)

    # 파일명 생성
    if len(files_to_zip) == 1:
        zip_filename = f"{files_to_zip[0].stem}.zip"
    else:
        zip_filename = f"pdfnmd_download_{len(files_to_zip)}files.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": _get_content_disposition(zip_filename, "attachment"),
            "Content-Length": str(len(zip_bytes)),
        },
    )
