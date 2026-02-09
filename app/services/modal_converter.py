"""
Modal 서버리스 GPU PDF 변환기

Modal을 사용하여 서버리스 GPU에서 marker-pdf를 실행합니다.
T4 GPU를 사용하여 빠른 PDF 변환을 제공합니다.

배포 방법:
    cd backend
    modal deploy app/services/modal_converter.py

로컬 테스트:
    modal run app/services/modal_converter.py --input-path /path/to/test.pdf
"""

import modal

# Modal 앱 정의
app = modal.App("pdfnmd-converter")

# GPU 이미지 정의 (marker-pdf + 필요 라이브러리)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "marker-pdf>=0.2.0",
        "torch",
        "Pillow",
    )
)


@app.function(
    image=image,
    gpu="T4",
    timeout=600,
    memory=8192,
)
def convert_pdf_with_modal(pdf_bytes: bytes) -> dict:
    """
    PDF를 Markdown으로 변환 (Modal GPU에서 실행)

    Args:
        pdf_bytes: PDF 파일 바이트 데이터

    Returns:
        dict: {
            "markdown": str,  # 변환된 마크다운 텍스트
            "images": dict[str, bytes],  # 추출된 이미지 {파일명: 바이트}
        }
    """
    import tempfile
    from pathlib import Path

    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict

    # 임시 파일로 PDF 저장
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        pdf_path = f.name

    try:
        # marker 모델 초기화 및 변환
        model_dict = create_model_dict()
        converter = PdfConverter(artifact_dict=model_dict)
        rendered = converter(pdf_path)

        # 마크다운 텍스트 추출
        try:
            from marker.output import text_from_rendered

            markdown_text, _, images = text_from_rendered(rendered)
        except ImportError:
            # text_from_rendered가 없는 경우 직접 접근
            markdown_text = rendered.markdown
            images = getattr(rendered, "images", {}) or {}

        # 이미지를 bytes로 변환 (PIL Image인 경우)
        images_bytes = {}
        for img_name, img_data in images.items():
            if isinstance(img_data, bytes):
                images_bytes[img_name] = img_data
            elif hasattr(img_data, "save"):
                # PIL Image 객체인 경우
                import io

                buffer = io.BytesIO()
                img_data.save(buffer, format="PNG")
                images_bytes[img_name] = buffer.getvalue()

        return {
            "markdown": markdown_text,
            "images": images_bytes,
        }

    finally:
        # 임시 파일 삭제
        Path(pdf_path).unlink(missing_ok=True)


# 로컬 테스트용 entrypoint
@app.local_entrypoint()
def main(input_path: str):
    """
    로컬 테스트용 entrypoint

    Usage:
        modal run app/services/modal_converter.py --input-path /path/to/test.pdf
    """
    from pathlib import Path

    pdf_path = Path(input_path)
    if not pdf_path.exists():
        print(f"파일을 찾을 수 없습니다: {input_path}")
        return

    print(f"PDF 변환 시작: {input_path}")

    # PDF 파일 읽기
    pdf_bytes = pdf_path.read_bytes()

    # Modal 함수 호출
    result = convert_pdf_with_modal.remote(pdf_bytes)

    print(f"변환 완료!")
    print(f"마크다운 길이: {len(result['markdown'])} 문자")
    print(f"이미지 수: {len(result['images'])}")

    # 결과 저장
    output_path = pdf_path.with_suffix(".md")
    output_path.write_text(result["markdown"], encoding="utf-8")
    print(f"저장 완료: {output_path}")
