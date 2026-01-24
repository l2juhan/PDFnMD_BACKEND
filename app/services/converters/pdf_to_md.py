import threading
from pathlib import Path
from typing import Dict

from app.core.exceptions import ConversionFailedException
from app.services.converters.base import BaseConverter


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

    def _convert_sync(self, input_path: Path, output_path: Path) -> None:
        """PDF를 Markdown으로 변환"""
        converter = self._get_converter()

        try:
            from marker.output import text_from_rendered

            # PDF 변환 실행
            rendered = converter(str(input_path))

            # 텍스트 및 이미지 추출
            text, _, images = text_from_rendered(rendered)

            # Markdown 저장
            output_path.write_text(text, encoding="utf-8")

            # 이미지 저장 (있는 경우)
            if images:
                self._save_images(images, output_path.parent, output_path.stem)

        except ImportError:
            # text_from_rendered 없는 경우 직접 접근
            try:
                rendered = converter(str(input_path))
                markdown_content = rendered.markdown
                output_path.write_text(markdown_content, encoding="utf-8")

                # 이미지 저장 (있는 경우)
                if hasattr(rendered, "images") and rendered.images:
                    self._save_images(
                        rendered.images, output_path.parent, output_path.stem
                    )
            except Exception as e:
                raise ConversionFailedException(f"PDF 변환 실패: {str(e)}")

        except Exception as e:
            raise ConversionFailedException(f"PDF 변환 실패: {str(e)}")

    def _save_images(
        self, images: Dict[str, bytes], output_dir: Path, prefix: str
    ) -> None:
        """추출된 이미지 저장"""
        images_dir = output_dir / f"{prefix}_images"
        images_dir.mkdir(parents=True, exist_ok=True)

        for img_name, img_data in images.items():
            img_path = images_dir / img_name
            if isinstance(img_data, bytes):
                img_path.write_bytes(img_data)
            elif hasattr(img_data, "save"):
                # PIL Image 객체인 경우
                img_data.save(str(img_path))
