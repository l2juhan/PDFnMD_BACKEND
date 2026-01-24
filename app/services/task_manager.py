import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.exceptions import TaskNotFoundException
from app.models import ConversionMode, TaskStatus


@dataclass
class Task:
    """변환 작업 데이터 모델"""

    task_id: str
    mode: ConversionMode
    original_filename: str
    status: TaskStatus = "pending"
    progress: int = 0
    input_path: Optional[Path] = None
    output_path: Optional[Path] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    @property
    def download_url(self) -> Optional[str]:
        """다운로드 URL 생성"""
        if self.status == "completed" and self.output_path:
            return f"/api/download/{self.task_id}"
        return None

    @property
    def is_expired(self) -> bool:
        """만료 여부 확인"""
        expiry_time = self.created_at + timedelta(hours=settings.FILE_RETENTION_HOURS)
        return datetime.now() > expiry_time

    def to_dict(self) -> dict:
        """딕셔너리 변환 (API 응답용)"""
        return {
            "task_id": self.task_id,
            "mode": self.mode,
            "status": self.status,
            "progress": self.progress,
            "download_url": self.download_url,
            "error": self.error,
            "filename": self.original_filename,
        }


class TaskManager:
    """
    변환 작업 관리자 (싱글톤)

    - 작업 생성 및 상태 관리
    - 작업 조회
    - 만료된 작업 자동 정리
    """

    _instance: Optional["TaskManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "TaskManager":
        """싱글톤 패턴"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._tasks: Dict[str, Task] = {}
        self._tasks_lock = threading.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._initialized = True

    def create_task(
        self,
        mode: ConversionMode,
        original_filename: str,
        input_path: Optional[Path] = None,
    ) -> Task:
        """
        새 변환 작업 생성

        Args:
            mode: 변환 모드
            original_filename: 원본 파일명
            input_path: 입력 파일 경로

        Returns:
            생성된 Task 객체
        """
        task_id = str(uuid.uuid4())

        task = Task(
            task_id=task_id,
            mode=mode,
            original_filename=original_filename,
            input_path=input_path,
        )

        with self._tasks_lock:
            self._tasks[task_id] = task

        return task

    def get_task(self, task_id: str) -> Task:
        """
        작업 조회

        Args:
            task_id: 작업 ID

        Returns:
            Task 객체

        Raises:
            TaskNotFoundException: 작업을 찾을 수 없는 경우
        """
        expired_task = None

        with self._tasks_lock:
            task = self._tasks.get(task_id)

            if task is None:
                raise TaskNotFoundException(task_id)

            # 만료된 작업은 잠금 내에서 삭제 처리
            if task.is_expired:
                self._tasks.pop(task_id, None)
                expired_task = task

        # 파일 정리는 잠금 밖에서 (I/O 작업)
        if expired_task is not None:
            self._cleanup_task_files(expired_task)
            raise TaskNotFoundException(task_id)

        return task

    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[int] = None,
        output_path: Optional[Path] = None,
        error: Optional[str] = None,
    ) -> Task:
        """
        작업 상태 업데이트

        Args:
            task_id: 작업 ID
            status: 새 상태
            progress: 진행률 (0-100)
            output_path: 출력 파일 경로
            error: 에러 메시지

        Returns:
            업데이트된 Task 객체
        """
        task = self.get_task(task_id)

        with self._tasks_lock:
            if status is not None:
                task.status = status
                if status == "completed":
                    task.completed_at = datetime.now()
                    task.progress = 100

            if progress is not None:
                task.progress = min(max(progress, 0), 100)

            if output_path is not None:
                task.output_path = output_path

            if error is not None:
                task.error = error
                task.status = "failed"

        return task

    def delete_task(self, task_id: str) -> bool:
        """
        작업 삭제 (관련 파일도 삭제)

        Args:
            task_id: 작업 ID

        Returns:
            삭제 성공 여부
        """
        with self._tasks_lock:
            task = self._tasks.pop(task_id, None)

        if task is None:
            return False

        # 관련 파일 삭제
        self._cleanup_task_files(task)
        return True

    def _cleanup_task_files(self, task: Task) -> None:
        """작업 관련 파일 삭제"""
        try:
            if task.input_path and task.input_path.exists():
                task.input_path.unlink()

            if task.output_path and task.output_path.exists():
                task.output_path.unlink()

                # 이미지 디렉토리 삭제 (PDF→MD 변환시)
                images_dir = task.output_path.parent / f"{task.output_path.stem}_images"
                if images_dir.exists():
                    import shutil
                    shutil.rmtree(images_dir)

        except Exception:
            pass  # 파일 삭제 실패는 무시

    def get_all_tasks(self) -> List[Task]:
        """모든 작업 조회"""
        with self._tasks_lock:
            return list(self._tasks.values())

    def cleanup_expired_tasks(self) -> int:
        """
        만료된 작업 정리

        Returns:
            삭제된 작업 수
        """
        expired_ids = []

        with self._tasks_lock:
            for task_id, task in self._tasks.items():
                if task.is_expired:
                    expired_ids.append(task_id)

        for task_id in expired_ids:
            self.delete_task(task_id)

        return len(expired_ids)

    async def start_cleanup_scheduler(self, interval_minutes: int = 10) -> None:
        """
        주기적 정리 스케줄러 시작

        Args:
            interval_minutes: 정리 간격 (분)
        """
        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval_minutes * 60)
                count = self.cleanup_expired_tasks()
                if count > 0:
                    print(f"[TaskManager] {count}개 만료 작업 삭제됨")

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    def stop_cleanup_scheduler(self) -> None:
        """정리 스케줄러 중지"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None


# 전역 TaskManager 인스턴스
task_manager = TaskManager()
