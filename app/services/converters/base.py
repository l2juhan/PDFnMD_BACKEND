import asyncio
import re
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ConversionFailedException, InvalidFileTypeException
from app.utils.file_validator import validate_file_for_conversion


class BaseConverter(ABC):
    """변환기 추상 베이스 클래스"""

    # 파일명 최대 길이
    MAX_FILENAME_LENGTH = 200

    @property
    @abstractmethod
    def input_extension(self) -> str:
        """입력 파일 확장자 (예: '.pdf')"""
        pass

    @property
    @abstractmethod
    def output_extension(self) -> str:
        """출력 파일 확장자 (예: '.md')"""
        pass

    @property
    @abstractmethod
    def mode(self) -> str:
        """변환 모드 (예: 'pdf-to-md')"""
        pass

    def _sanitize_filename(self, filename: str) -> str:
        """
        파일명 정제 (Path Traversal 방지)

        - 경로 구분자 제거
        - 위험 문자 제거
        - '..' 시퀀스 제거
        - 길이 제한
        """
        if not filename:
            return "unnamed"

        # 경로 구분자 및 위험 문자 제거
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)

        # '..' 시퀀스 제거 (Path Traversal 방지)
        sanitized = sanitized.replace("..", "_")

        # 앞뒤 공백 및 점 제거
        sanitized = sanitized.strip(". ")

        # 빈 문자열이면 기본값
        if not sanitized:
            return "unnamed"

        # 길이 제한
        return sanitized[: self.MAX_FILENAME_LENGTH]

    def validate_input(self, input_path: Path) -> None:
        """입력 파일 검증 (확장자 + 시그니처/MIME)"""
        # 기본 파일 검증 + 시그니처 검증
        is_valid, error_msg = validate_file_for_conversion(
            input_path, self.input_extension
        )
        if not is_valid:
            if "확장자" in error_msg:
                raise InvalidFileTypeException(
                    expected_type=self.input_extension.upper().replace(".", ""),
                    mode=self.mode,
                )
            raise ConversionFailedException(error_msg)

        # 심볼릭 링크 검증 (경로 탈출 방지)
        # 입력 파일이 uploads 디렉토리 내에 있는지 확인
        try:
            resolved = input_path.resolve()
            upload_dir_resolved = settings.UPLOAD_DIR.resolve()
            if not str(resolved).startswith(str(upload_dir_resolved)):
                raise ConversionFailedException("잘못된 파일 경로입니다")
        except (OSError, ValueError):
            raise ConversionFailedException("파일 경로를 확인할 수 없습니다")

    def get_output_path(self, input_path: Path, output_dir: Path) -> Path:
        """출력 파일 경로 생성 (안전한 파일명 사용)"""
        safe_stem = self._sanitize_filename(input_path.stem)
        return output_dir / f"{safe_stem}{self.output_extension}"

    @abstractmethod
    def _convert_sync(
        self, input_path: Path, output_path: Path, task_id: str | None = None
    ) -> None:
        """동기 변환 실행 (서브클래스에서 구현)"""
        pass

    async def convert(
        self, input_path: Path, output_dir: Path, task_id: str | None = None
    ) -> Path:
        """
        비동기 변환 실행

        Args:
            input_path: 입력 파일 경로
            output_dir: 출력 디렉토리 경로
            task_id: 작업 ID (S3 업로드 등에 사용)

        Returns:
            출력 파일 경로
        """
        self.validate_input(input_path)

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.get_output_path(input_path, output_dir)

        # 출력 경로가 출력 디렉토리 내에 있는지 확인
        if not str(output_path.resolve()).startswith(str(output_dir.resolve())):
            raise ConversionFailedException("잘못된 출력 경로입니다")

        try:
            await asyncio.to_thread(self._convert_sync, input_path, output_path, task_id)
        except Exception as e:
            if isinstance(e, ConversionFailedException):
                raise
            raise ConversionFailedException(f"변환 중 오류 발생: {str(e)}")

        if not output_path.exists():
            raise ConversionFailedException("변환 결과 파일이 생성되지 않았습니다")

        return output_path
