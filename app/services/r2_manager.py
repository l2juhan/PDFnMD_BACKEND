"""Cloudflare R2 파일 관리 서비스"""

import logging
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class R2Manager:
    """Cloudflare R2 파일 업로드/삭제 관리 (S3 호환 API 사용)"""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        """R2 클라이언트 지연 로딩"""
        if self._client is None:
            if not settings.is_r2_enabled:
                raise RuntimeError(
                    "R2가 설정되지 않았습니다. R2 환경 변수를 확인하세요."
                )
            self._client = boto3.client(
                "s3",
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                endpoint_url=settings.R2_ENDPOINT_URL,
            )
        return self._client

    def upload_image(
        self,
        image_data: bytes,
        task_id: str,
        filename: str,
        content_type: str = "image/png",
    ) -> str:
        """
        이미지를 R2에 업로드하고 퍼블릭 URL 반환

        Args:
            image_data: 이미지 바이트 데이터
            task_id: 작업 ID (R2 경로에 사용)
            filename: 파일명
            content_type: MIME 타입

        Returns:
            R2 퍼블릭 URL
        """
        r2_key = f"temp/{task_id}/{filename}"

        try:
            self.client.put_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=r2_key,
                Body=image_data,
                ContentType=content_type,
            )

            url = f"{settings.R2_PUBLIC_URL}/{r2_key}"
            logger.info(f"R2 업로드 완료: {r2_key}")
            return url

        except ClientError as e:
            logger.error(f"R2 업로드 실패: {e}")
            raise

    def upload_images(
        self,
        images: dict,
        task_id: str,
    ) -> dict:
        """
        여러 이미지를 R2에 업로드하고 URL 매핑 반환

        Args:
            images: {파일명: 이미지 데이터} 딕셔너리
            task_id: 작업 ID

        Returns:
            {원본 파일명: R2 URL} 딕셔너리
        """
        url_mapping = {}

        for filename, image_data in images.items():
            # 이미지 데이터 추출
            if isinstance(image_data, bytes):
                data = image_data
            elif hasattr(image_data, "tobytes"):
                # PIL Image 객체인 경우
                import io

                buffer = io.BytesIO()
                image_data.save(buffer, format="PNG")
                data = buffer.getvalue()
            else:
                logger.warning(f"지원하지 않는 이미지 형식: {filename}")
                continue

            # Content-Type 결정
            ext = filename.lower().split(".")[-1] if "." in filename else "png"
            content_types = {
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "gif": "image/gif",
                "webp": "image/webp",
            }
            content_type = content_types.get(ext, "image/png")

            try:
                url = self.upload_image(data, task_id, filename, content_type)
                url_mapping[filename] = url
            except ClientError:
                logger.error(f"이미지 업로드 실패, 건너뜀: {filename}")
                continue

        return url_mapping

    def delete_task_images(self, task_id: str) -> int:
        """
        특정 task의 모든 이미지 삭제

        Args:
            task_id: 작업 ID

        Returns:
            삭제된 파일 수
        """
        prefix = f"temp/{task_id}/"
        deleted_count = 0

        try:
            # 해당 prefix의 모든 객체 목록 조회
            paginator = self.client.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=settings.R2_BUCKET_NAME,
                Prefix=prefix,
            )

            objects_to_delete = []
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        objects_to_delete.append({"Key": obj["Key"]})

            if objects_to_delete:
                # 최대 1000개씩 삭제 (S3 API 제한)
                for i in range(0, len(objects_to_delete), 1000):
                    batch = objects_to_delete[i : i + 1000]
                    self.client.delete_objects(
                        Bucket=settings.R2_BUCKET_NAME,
                        Delete={"Objects": batch},
                    )
                    deleted_count += len(batch)

            logger.info(f"R2 이미지 삭제 완료: task_id={task_id}, 삭제된 파일 수={deleted_count}")

        except ClientError as e:
            logger.error(f"R2 이미지 삭제 실패: {e}")
            raise

        return deleted_count

    def list_task_images(self, task_id: str) -> List[str]:
        """
        특정 task의 모든 이미지 URL 목록 반환

        Args:
            task_id: 작업 ID

        Returns:
            R2 URL 목록
        """
        prefix = f"temp/{task_id}/"
        urls = []

        try:
            paginator = self.client.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=settings.R2_BUCKET_NAME,
                Prefix=prefix,
            )

            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        url = f"{settings.R2_PUBLIC_URL}/{obj['Key']}"
                        urls.append(url)

        except ClientError as e:
            logger.error(f"R2 이미지 목록 조회 실패: {e}")
            raise

        return urls


# 싱글톤 인스턴스
_r2_manager: Optional[R2Manager] = None


def get_r2_manager() -> R2Manager:
    """R2Manager 싱글톤 반환"""
    global _r2_manager
    if _r2_manager is None:
        _r2_manager = R2Manager()
    return _r2_manager
