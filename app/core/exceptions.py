from fastapi import HTTPException, status


class PDFnMDException(HTTPException):
    """PDFnMD 기본 예외"""

    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: str = "서버 오류가 발생했습니다",
    ):
        super().__init__(status_code=status_code, detail=detail)


class FileTooLargeException(PDFnMDException):
    """파일 크기 초과 예외"""

    def __init__(self, max_size_mb: int):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"파일 크기가 {max_size_mb}MB를 초과합니다",
        )


class InvalidFileTypeException(PDFnMDException):
    """잘못된 파일 타입 예외"""

    def __init__(self, expected_type: str, mode: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{expected_type} 파일만 업로드 가능합니다 (현재 모드: {mode})",
        )


class TaskNotFoundException(PDFnMDException):
    """작업을 찾을 수 없음 예외"""

    def __init__(self, task_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"작업을 찾을 수 없습니다: {task_id}",
        )


class ConversionFailedException(PDFnMDException):
    """변환 실패 예외 (클라이언트 요청 오류)"""

    def __init__(self, message: str = "파일 변환에 실패했습니다"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
