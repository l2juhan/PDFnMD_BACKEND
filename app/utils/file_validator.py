from pathlib import Path
from typing import Optional

# 파일 시그니처 (매직 바이트)
FILE_SIGNATURES = {
    ".pdf": [b"%PDF"],
    ".md": None,  # 텍스트 파일은 시그니처 없음
}

# MIME 타입 매핑
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".md": "text/markdown",
}


def validate_file_signature(file_path: Path, expected_extension: str) -> bool:
    """
    파일 시그니처(매직 바이트) 검증

    Args:
        file_path: 검증할 파일 경로
        expected_extension: 예상 확장자 (예: '.pdf')

    Returns:
        시그니처가 유효하면 True
    """
    signatures = FILE_SIGNATURES.get(expected_extension.lower())

    # 시그니처가 정의되지 않은 확장자는 통과
    if signatures is None:
        return True

    try:
        with open(file_path, "rb") as f:
            header = f.read(16)

        for sig in signatures:
            if header.startswith(sig):
                return True

        return False
    except (IOError, OSError):
        return False


def get_mime_type(extension: str) -> Optional[str]:
    """확장자에 해당하는 MIME 타입 반환"""
    return MIME_TYPES.get(extension.lower())


def is_text_file(file_path: Path, sample_size: int = 8192) -> bool:
    """
    파일이 텍스트 파일인지 확인

    Args:
        file_path: 확인할 파일 경로
        sample_size: 확인할 바이트 수

    Returns:
        텍스트 파일이면 True
    """
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(sample_size)

        # NULL 바이트가 있으면 바이너리
        if b"\x00" in chunk:
            return False

        # UTF-8로 디코딩 시도
        try:
            chunk.decode("utf-8")
            return True
        except UnicodeDecodeError:
            pass

        # Latin-1으로 디코딩 시도
        try:
            chunk.decode("latin-1")
            return True
        except UnicodeDecodeError:
            return False

    except (IOError, OSError):
        return False


def validate_file_for_conversion(
    file_path: Path, expected_extension: str
) -> tuple[bool, str]:
    """
    변환을 위한 파일 검증

    Args:
        file_path: 검증할 파일 경로
        expected_extension: 예상 확장자

    Returns:
        (유효 여부, 에러 메시지)
    """
    if not file_path.exists():
        return False, "파일이 존재하지 않습니다"

    if not file_path.is_file():
        return False, "유효한 파일이 아닙니다"

    # 확장자 검증
    if file_path.suffix.lower() != expected_extension.lower():
        return False, f"잘못된 파일 확장자입니다. {expected_extension} 파일이 필요합니다"

    # PDF 파일 시그니처 검증
    if expected_extension.lower() == ".pdf":
        if not validate_file_signature(file_path, expected_extension):
            return False, "유효한 PDF 파일이 아닙니다"

    # Markdown 파일 텍스트 검증
    if expected_extension.lower() == ".md":
        if not is_text_file(file_path):
            return False, "유효한 텍스트 파일이 아닙니다"

    return True, ""
