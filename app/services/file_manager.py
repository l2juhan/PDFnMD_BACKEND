import asyncio
import re
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO, List, Optional, Tuple

import aiofiles

from app.core.config import settings
from app.core.exceptions import FileTooLargeException, TooManyFilesException


class FileManager:
    """
    파일 관리자

    - 파일 업로드 저장
    - 파일 삭제 및 정리
    - ZIP 압축
    """

    # 파일명 최대 길이
    MAX_FILENAME_LENGTH = 200

    def __init__(
        self,
        upload_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        self.upload_dir = upload_dir or settings.UPLOAD_DIR
        self.output_dir = output_dir or settings.OUTPUT_DIR

        # 디렉토리 생성
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        """
        파일명 정제 (보안)

        - 경로 구분자 제거
        - 위험 문자 제거
        - 길이 제한
        """
        if not filename:
            return "unnamed"

        # 경로 구분자 및 위험 문자 제거
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)

        # '..' 시퀀스 제거
        sanitized = sanitized.replace("..", "_")

        # 앞뒤 공백 및 점 제거
        sanitized = sanitized.strip(". ")

        if not sanitized:
            return "unnamed"

        return sanitized[: self.MAX_FILENAME_LENGTH]

    def _generate_unique_filename(self, original_filename: str) -> str:
        """고유 파일명 생성 (UUID 접두사)"""
        sanitized = self._sanitize_filename(original_filename)
        unique_id = uuid.uuid4().hex[:8]
        stem = Path(sanitized).stem
        suffix = Path(sanitized).suffix
        return f"{unique_id}_{stem}{suffix}"

    async def save_upload(
        self,
        file: BinaryIO,
        filename: str,
        max_size: Optional[int] = None,
    ) -> Tuple[Path, int]:
        """
        업로드 파일 저장

        Args:
            file: 파일 객체 (read() 메서드 필요)
            filename: 원본 파일명
            max_size: 최대 크기 (bytes), None이면 설정값 사용

        Returns:
            (저장 경로, 파일 크기)

        Raises:
            FileTooLargeException: 파일 크기 초과
        """
        max_size = max_size or settings.MAX_FILE_SIZE_BYTES
        unique_filename = self._generate_unique_filename(filename)
        save_path = self.upload_dir / unique_filename

        total_size = 0
        chunk_size = 1024 * 1024  # 1MB 청크
        size_exceeded = False

        try:
            async with aiofiles.open(save_path, "wb") as f:
                while True:
                    # 동기 read를 비동기로 실행
                    chunk = await asyncio.to_thread(file.read, chunk_size)
                    if not chunk:
                        break

                    total_size += len(chunk)

                    if total_size > max_size:
                        # 크기 초과 플래그 설정 후 루프 탈출
                        # async with가 자동으로 파일을 닫음
                        size_exceeded = True
                        break

                    await f.write(chunk)
        finally:
            # 크기 초과 또는 예외 발생 시 파일 정리
            if size_exceeded:
                save_path.unlink(missing_ok=True)
                raise FileTooLargeException(settings.MAX_FILE_SIZE_MB)

        return save_path, total_size

    async def save_uploads_batch(
        self,
        files: List[Tuple[BinaryIO, str]],
        max_files: Optional[int] = None,
        max_total_size: Optional[int] = None,
    ) -> List[Tuple[Path, int]]:
        """
        여러 파일 일괄 저장

        Args:
            files: [(file_object, filename), ...] 리스트
            max_files: 최대 파일 수
            max_total_size: 총 최대 크기

        Returns:
            [(저장 경로, 파일 크기), ...] 리스트
        """
        max_files = max_files or settings.MAX_FILES
        max_total_size = max_total_size or settings.MAX_TOTAL_SIZE_BYTES

        if len(files) > max_files:
            raise TooManyFilesException(max_files)

        results = []
        total_size = 0
        saved_paths = []

        try:
            for file_obj, filename in files:
                path, size = await self.save_upload(file_obj, filename)
                total_size += size

                if total_size > max_total_size:
                    # 총 크기 초과시 저장된 파일들 삭제
                    path.unlink(missing_ok=True)
                    raise FileTooLargeException(settings.MAX_TOTAL_SIZE_MB)

                results.append((path, size))
                saved_paths.append(path)

        except Exception:
            # 에러 발생시 저장된 파일들 정리
            for path in saved_paths:
                path.unlink(missing_ok=True)
            raise

        return results

    def delete_file(self, file_path: Path) -> bool:
        """
        파일 삭제

        Args:
            file_path: 삭제할 파일 경로

        Returns:
            삭제 성공 여부
        """
        try:
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False

    def delete_directory(self, dir_path: Path) -> bool:
        """
        디렉토리 삭제 (내용 포함)

        Args:
            dir_path: 삭제할 디렉토리 경로

        Returns:
            삭제 성공 여부
        """
        try:
            if dir_path.exists() and dir_path.is_dir():
                shutil.rmtree(dir_path)
                return True
            return False
        except Exception:
            return False

    def cleanup_old_files(
        self,
        directory: Optional[Path] = None,
        max_age_hours: Optional[int] = None,
    ) -> int:
        """
        오래된 파일 정리

        Args:
            directory: 정리할 디렉토리 (None이면 upload/output 둘 다)
            max_age_hours: 최대 보관 시간

        Returns:
            삭제된 파일 수
        """
        max_age = max_age_hours or settings.FILE_RETENTION_HOURS
        cutoff_time = datetime.now() - timedelta(hours=max_age)
        deleted_count = 0

        directories = [directory] if directory else [self.upload_dir, self.output_dir]

        for dir_path in directories:
            if not dir_path.exists():
                continue

            for item in dir_path.iterdir():
                try:
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    if mtime < cutoff_time:
                        if item.is_file():
                            item.unlink()
                            deleted_count += 1
                        elif item.is_dir():
                            shutil.rmtree(item)
                            deleted_count += 1
                except Exception:
                    continue

        return deleted_count

    def get_file_info(self, file_path: Path) -> Optional[dict]:
        """
        파일 정보 조회

        Args:
            file_path: 파일 경로

        Returns:
            파일 정보 딕셔너리 또는 None
        """
        if not file_path.exists():
            return None

        stat = file_path.stat()
        return {
            "path": str(file_path),
            "name": file_path.name,
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime),
            "modified_at": datetime.fromtimestamp(stat.st_mtime),
        }


# 전역 FileManager 인스턴스
file_manager = FileManager()
