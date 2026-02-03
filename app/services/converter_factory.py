import threading
from typing import Dict, Type

from app.models import ConversionMode
from app.services.converters.base import BaseConverter
from app.services.converters.pdf_to_md import PdfToMarkdownConverter


class ConverterFactory:
    """변환기 팩토리 (싱글톤 패턴)"""

    _converters: Dict[ConversionMode, Type[BaseConverter]] = {
        "pdf-to-md": PdfToMarkdownConverter,
    }

    # 인스턴스 캐시 (싱글톤)
    _instances: Dict[ConversionMode, BaseConverter] = {}
    _lock = threading.Lock()

    @classmethod
    def get_converter(cls, mode: ConversionMode) -> BaseConverter:
        """
        변환 모드에 맞는 변환기 인스턴스 반환 (싱글톤)

        Args:
            mode: 변환 모드 ('pdf-to-md')

        Returns:
            BaseConverter 인스턴스 (캐시됨)

        Raises:
            ValueError: 지원하지 않는 변환 모드
        """
        if mode not in cls._converters:
            raise ValueError(f"지원하지 않는 변환 모드: {mode}")

        # 스레드 안전한 싱글톤
        if mode not in cls._instances:
            with cls._lock:
                # Double-check locking
                if mode not in cls._instances:
                    cls._instances[mode] = cls._converters[mode]()

        return cls._instances[mode]

    @classmethod
    def get_accepted_extension(cls, mode: ConversionMode) -> str:
        """
        변환 모드에서 허용하는 입력 파일 확장자 반환

        Args:
            mode: 변환 모드

        Returns:
            확장자 문자열 (예: '.pdf')
        """
        converter = cls.get_converter(mode)
        return converter.input_extension

    @classmethod
    def get_output_extension(cls, mode: ConversionMode) -> str:
        """
        변환 모드의 출력 파일 확장자 반환

        Args:
            mode: 변환 모드

        Returns:
            확장자 문자열 (예: '.md')
        """
        converter = cls.get_converter(mode)
        return converter.output_extension

    @classmethod
    def get_supported_modes(cls) -> list[ConversionMode]:
        """지원하는 모든 변환 모드 반환"""
        return list(cls._converters.keys())

    @classmethod
    def clear_instances(cls) -> None:
        """인스턴스 캐시 초기화 (테스트용)"""
        with cls._lock:
            cls._instances.clear()
