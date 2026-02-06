import logging
import re
import threading
from pathlib import Path
from typing import Dict

from app.core.config import settings
from app.core.exceptions import ConversionFailedException
from app.services.converters.base import BaseConverter

logger = logging.getLogger(__name__)


class PdfToMarkdownConverter(BaseConverter):
    """PDF → Markdown 변환기 (marker-pdf 사용)"""

    # 클래스 레벨 잠금 (모델 초기화 스레드 안전성)
    _init_lock = threading.Lock()

    def __init__(self):
        self._converter = None
        self._model_dict = None

    @property
    def input_extension(self) -> str:
        return ".pdf"

    @property
    def output_extension(self) -> str:
        return ".md"

    @property
    def mode(self) -> str:
        return "pdf-to-md"

    def _get_converter(self):
        """marker 변환기 지연 로딩 (모델 캐싱, 스레드 안전)"""
        if self._converter is None:
            with self._init_lock:
                # Double-check locking
                if self._converter is None:
                    try:
                        from marker.converters.pdf import PdfConverter
                        from marker.models import create_model_dict

                        # 모델 딕셔너리 생성 (첫 실행시 모델 다운로드)
                        if self._model_dict is None:
                            self._model_dict = create_model_dict()

                        self._converter = PdfConverter(
                            artifact_dict=self._model_dict,
                        )
                    except ImportError as e:
                        raise ConversionFailedException(
                            "marker-pdf 라이브러리가 설치되지 않았습니다. "
                            "pip install marker-pdf를 실행하세요."
                        )
                    except Exception as e:
                        raise ConversionFailedException(
                            f"marker 초기화 실패: {str(e)}"
                        )
        return self._converter

    def _convert_sync(
        self, input_path: Path, output_path: Path, task_id: str | None = None
    ) -> None:
        """PDF를 Markdown으로 변환"""
        converter = self._get_converter()

        try:
            from marker.output import text_from_rendered

            # PDF 변환 실행
            rendered = converter(str(input_path))

            # 텍스트 및 이미지 추출
            text, _, images = text_from_rendered(rendered)

            # 이미지 처리 (R2 업로드 또는 로컬 저장)
            if images:
                text = self._process_images(
                    text, images, output_path.parent, output_path.stem, task_id
                )

            # Markdown 저장
            output_path.write_text(text, encoding="utf-8")

        except ImportError:
            # text_from_rendered 없는 경우 직접 접근
            try:
                rendered = converter(str(input_path))
                markdown_content = rendered.markdown

                # 이미지 처리 (있는 경우)
                if hasattr(rendered, "images") and rendered.images:
                    markdown_content = self._process_images(
                        markdown_content,
                        rendered.images,
                        output_path.parent,
                        output_path.stem,
                        task_id,
                    )

                output_path.write_text(markdown_content, encoding="utf-8")

            except Exception as e:
                raise ConversionFailedException(f"PDF 변환 실패: {str(e)}")

        except Exception as e:
            raise ConversionFailedException(f"PDF 변환 실패: {str(e)}")

    def _process_images(
        self,
        markdown_text: str,
        images: Dict[str, bytes],
        output_dir: Path,
        prefix: str,
        task_id: str | None = None,
    ) -> str:
        """
        이미지 처리: R2 업로드 또는 로컬 저장 후 URL 교체

        Args:
            markdown_text: 원본 마크다운 텍스트
            images: {파일명: 이미지 데이터} 딕셔너리
            output_dir: 출력 디렉토리
            prefix: 파일명 프리픽스
            task_id: 작업 ID (R2 업로드 시 사용)

        Returns:
            이미지 URL이 교체된 마크다운 텍스트
        """
        if not images:
            return markdown_text

        # R2가 활성화되어 있고 task_id가 있으면 R2에 업로드
        if settings.is_r2_enabled and task_id:
            return self._upload_images_to_r2(markdown_text, images, task_id)
        else:
            # 로컬에 이미지 저장
            self._save_images(images, output_dir, prefix)
            return markdown_text

    def _upload_images_to_r2(
        self,
        markdown_text: str,
        images: Dict[str, bytes],
        task_id: str,
    ) -> str:
        """
        이미지를 R2에 업로드하고 마크다운 내 URL 교체

        Args:
            markdown_text: 원본 마크다운 텍스트
            images: {파일명: 이미지 데이터} 딕셔너리
            task_id: 작업 ID

        Returns:
            R2 URL로 교체된 마크다운 텍스트
        """
        try:
            from app.services.r2_manager import get_r2_manager

            r2_manager = get_r2_manager()
            url_mapping = r2_manager.upload_images(images, task_id)

            if url_mapping:
                markdown_text = self._replace_image_urls(markdown_text, url_mapping)
                logger.info(f"R2 이미지 업로드 완료: task_id={task_id}, 파일 수={len(url_mapping)}")

            return markdown_text

        except Exception as e:
            logger.error(f"R2 이미지 업로드 실패: {e}")
            # R2 업로드 실패 시에도 변환은 계속 진행 (이미지 없이)
            return markdown_text

    def _replace_image_urls(
        self,
        markdown_text: str,
        url_mapping: Dict[str, str],
    ) -> str:
        """
        마크다운 텍스트 내 이미지 경로를 R2 URL로 교체

        Args:
            markdown_text: 원본 마크다운 텍스트
            url_mapping: {원본 파일명: R2 URL} 딕셔너리

        Returns:
            URL이 교체된 마크다운 텍스트
        """
        for original_name, r2_url in url_mapping.items():
            # marker가 생성하는 다양한 이미지 경로 패턴 처리
            # 예: ![이미지](images/image_001.png), ![](./images/image_001.png)
            patterns = [
                # 정확한 파일명 매칭
                rf"!\[([^\]]*)\]\([^)]*{re.escape(original_name)}\)",
                # 경로 포함 매칭
                rf"!\[([^\]]*)\]\([^)]*/{re.escape(original_name)}\)",
            ]

            for pattern in patterns:
                markdown_text = re.sub(
                    pattern,
                    rf"![\1]({r2_url})",
                    markdown_text,
                )

        return markdown_text

    def _save_images(
        self, images: Dict[str, bytes], output_dir: Path, prefix: str
    ) -> None:
        """추출된 이미지를 로컬에 저장 (R2 미사용 시)"""
        images_dir = output_dir / f"{prefix}_images"
        images_dir.mkdir(parents=True, exist_ok=True)

        for img_name, img_data in images.items():
            img_path = images_dir / img_name
            if isinstance(img_data, bytes):
                img_path.write_bytes(img_data)
            elif hasattr(img_data, "save"):
                # PIL Image 객체인 경우
                img_data.save(str(img_path))
