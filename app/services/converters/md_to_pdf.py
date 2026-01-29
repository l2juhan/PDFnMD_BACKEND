from pathlib import Path
from typing import List

from app.core.config import settings
from app.core.exceptions import ConversionFailedException
from app.services.converters.base import BaseConverter


class MarkdownToPdfConverter(BaseConverter):
    """Markdown → PDF 변환기 (pypandoc + XeLaTeX)"""

    @property
    def input_extension(self) -> str:
        return ".md"

    @property
    def output_extension(self) -> str:
        return ".pdf"

    @property
    def mode(self) -> str:
        return "md-to-pdf"

    def _build_extra_args(self) -> List[str]:
        """Pandoc 추가 인자 생성"""
        args = [
            f"--pdf-engine={settings.PANDOC_PDF_ENGINE}",
            "--standalone",
        ]

        # 한글 폰트 설정
        if settings.PANDOC_FONT:
            args.extend([
                f"-V mainfont={settings.PANDOC_FONT}",
                f"-V sansfont={settings.PANDOC_FONT}",
                f"-V monofont={settings.PANDOC_FONT}",
            ])
        else:
            # 기본 한글 폰트 (시스템에 설치된 경우)
            args.extend([
                "-V mainfont=NanumGothic",
                "-V sansfont=NanumGothic",
                "-V monofont=D2Coding",
            ])

        # 문서 스타일링
        args.extend([
            "-V geometry:margin=2.5cm",
            "-V fontsize=11pt",
            "-V linestretch=1.5",
        ])

        return args

    def _convert_sync(
        self, input_path: Path, output_path: Path, task_id: str | None = None
    ) -> None:
        """Markdown을 PDF로 변환"""
        try:
            import pypandoc
        except ImportError:
            raise ConversionFailedException(
                "pypandoc 라이브러리가 설치되지 않았습니다. "
                "pip install pypandoc를 실행하세요."
            )

        # Pandoc 설치 확인
        try:
            pypandoc.get_pandoc_version()
        except OSError:
            raise ConversionFailedException(
                "Pandoc이 설치되지 않았습니다. "
                "brew install pandoc (Mac) 또는 "
                "apt install pandoc (Ubuntu)를 실행하세요."
            )

        extra_args = self._build_extra_args()

        try:
            pypandoc.convert_file(
                str(input_path),
                "pdf",
                outputfile=str(output_path),
                extra_args=extra_args,
            )
        except Exception as e:
            self._handle_conversion_error(e)

    def _handle_conversion_error(self, error: Exception) -> None:
        """변환 에러 처리"""
        error_msg = str(error).lower()

        if "xelatex" in error_msg or "xetex" in error_msg:
            raise ConversionFailedException(
                "XeLaTeX가 설치되지 않았습니다. "
                "brew install --cask mactex (Mac) 또는 "
                "apt install texlive-xetex (Ubuntu)를 실행하세요."
            )

        if "font" in error_msg and ("not found" in error_msg or "cannot" in error_msg):
            raise ConversionFailedException(
                "한글 폰트를 찾을 수 없습니다. "
                "apt install fonts-nanum (Ubuntu)를 실행하거나 "
                "PANDOC_FONT 환경변수를 설정하세요."
            )

        if "pandoc" in error_msg:
            raise ConversionFailedException(
                "Pandoc 실행 오류: " + str(error)
            )

        raise ConversionFailedException(f"PDF 생성 실패: {str(error)}")
