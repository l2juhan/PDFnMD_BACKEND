# CLAUDE.md - PDFnMD (Backend)

## 프로젝트 개요

**PDFnMD** - PDF ↔ Markdown 양방향 변환 무료 웹 서비스의 **백엔드**.

### 지원 변환
- **PDF → MD**: marker 라이브러리 (고품질, 테이블/이미지 지원)
- **MD → PDF**: Pandoc (문서화용, 깔끔한 출력)

### 사용 제한
- 파일 수: 최대 20개
- 파일당 용량: 최대 20MB
- 총 용량: 최대 100MB
- 파일 보관: 1시간 후 자동 삭제

## 기술 스택

- **Framework**: FastAPI (Python 3.11+)
- **PDF → MD**: marker-pdf
- **MD → PDF**: pypandoc (Pandoc wrapper)
- **비동기 작업**: Celery + Redis (확장시)
- **파일 저장**: 로컬 → S3 (배포시)
- **ASGI 서버**: Uvicorn
- **검증**: Pydantic v2

## 프로젝트 구조

```
backend/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── convert.py        # 변환 API
│   │   │   ├── status.py         # 상태 조회
│   │   │   └── download.py       # 다운로드
│   │   └── deps.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── exceptions.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── converters/
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # 추상 베이스
│   │   │   ├── pdf_to_md.py      # PDF→MD (marker)
│   │   │   └── md_to_pdf.py      # MD→PDF (Pandoc)
│   │   ├── converter_factory.py  # 변환기 팩토리
│   │   ├── file_manager.py
│   │   └── task_manager.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── request.py
│   │   └── response.py
│   │
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
│
├── uploads/
├── outputs/
├── tests/
├── main.py
├── requirements.txt
├── .env.example
├── Dockerfile
└── CLAUDE.md
```

## 핵심 기능

### MVP (1차)
1. [ ] PDF → MD 변환 (marker)
2. [ ] MD → PDF 변환 (Pandoc)
3. [ ] 변환 모드 파라미터
4. [ ] 작업 상태 관리
5. [ ] 단일/다중 파일 다운로드 (ZIP)
6. [ ] 파일 자동 삭제 (1시간)

### 확장 (2차)
1. [ ] Celery 비동기 처리
2. [ ] S3 파일 저장
3. [ ] Rate limiting
4. [ ] PDF 스타일 옵션 (MD→PDF)

## API 설계

### POST /api/convert
파일 업로드 및 변환 시작

```python
# Request
Content-Type: multipart/form-data
file: UploadFile (PDF 또는 MD)
mode: str  # 'pdf-to-md' | 'md-to-pdf'

# Response 200
{
    "task_id": "uuid4",
    "mode": "pdf-to-md",
    "status": "processing",
    "message": "변환이 시작되었습니다"
}

# Response 400
{
    "detail": "PDF 파일만 업로드 가능합니다 (현재 모드: pdf-to-md)"
}
```

### GET /api/status/{task_id}
변환 상태 조회

```python
# Response 200
{
    "task_id": "uuid4",
    "mode": "pdf-to-md",
    "status": "completed",
    "progress": 100,
    "download_url": "/api/download/{task_id}",
    "error": null
}
```

### GET /api/download/{task_id}
변환된 파일 다운로드

```python
# PDF→MD: text/markdown
# MD→PDF: application/pdf
Content-Disposition: attachment; filename="filename.md"
```

### POST /api/download/batch
여러 파일 ZIP으로 다운로드

```python
# Request
{
    "task_ids": ["uuid1", "uuid2"]
}

# Response: application/zip
```

## 변환기 설계 (팩토리 패턴)

### 추상 베이스
```python
# services/converters/base.py

from abc import ABC, abstractmethod
from pathlib import Path

class BaseConverter(ABC):
    @abstractmethod
    async def convert(self, input_path: Path, output_dir: Path) -> Path:
        """변환 실행, 출력 파일 경로 반환"""
        pass
    
    @property
    @abstractmethod
    def input_extension(self) -> str:
        """입력 파일 확장자"""
        pass
    
    @property
    @abstractmethod
    def output_extension(self) -> str:
        """출력 파일 확장자"""
        pass
```

### PDF → MD 변환기
```python
# services/converters/pdf_to_md.py

class PdfToMarkdownConverter(BaseConverter):
    def __init__(self):
        from marker.converters.pdf import PdfConverter
        self.converter = PdfConverter()
    
    async def convert(self, input_path: Path, output_dir: Path) -> Path:
        result = self.converter(str(input_path))
        output_path = output_dir / f"{input_path.stem}.md"
        output_path.write_text(result.markdown, encoding='utf-8')
        return output_path
    
    @property
    def input_extension(self) -> str:
        return '.pdf'
    
    @property
    def output_extension(self) -> str:
        return '.md'
```

### MD → PDF 변환기
```python
# services/converters/md_to_pdf.py

class MarkdownToPdfConverter(BaseConverter):
    async def convert(self, input_path: Path, output_dir: Path) -> Path:
        import pypandoc
        
        output_path = output_dir / f"{input_path.stem}.pdf"
        pypandoc.convert_file(
            str(input_path),
            'pdf',
            outputfile=str(output_path),
            extra_args=['--pdf-engine=xelatex']  # 한글 지원
        )
        return output_path
    
    @property
    def input_extension(self) -> str:
        return '.md'
    
    @property
    def output_extension(self) -> str:
        return '.pdf'
```

### 팩토리
```python
# services/converter_factory.py

from typing import Literal

ConversionMode = Literal['pdf-to-md', 'md-to-pdf']

class ConverterFactory:
    _converters = {
        'pdf-to-md': PdfToMarkdownConverter,
        'md-to-pdf': MarkdownToPdfConverter,
    }
    
    @classmethod
    def get_converter(cls, mode: ConversionMode) -> BaseConverter:
        if mode not in cls._converters:
            raise ValueError(f"지원하지 않는 변환 모드: {mode}")
        return cls._converters[mode]()
    
    @classmethod
    def get_accepted_extension(cls, mode: ConversionMode) -> str:
        converter = cls.get_converter(mode)
        return converter.input_extension
```

## 환경 변수

```env
# .env.example

# 서버
ENV=development
HOST=0.0.0.0
PORT=8000

# CORS
ALLOWED_ORIGINS=http://localhost:5173

# 파일 제한
MAX_FILE_SIZE_MB=20
MAX_FILES=20
MAX_TOTAL_SIZE_MB=100

# 경로
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs

# 파일 보관 시간
FILE_RETENTION_HOURS=1

# marker
MARKER_USE_GPU=false

# Pandoc (한글 폰트)
PANDOC_PDF_ENGINE=xelatex
# PANDOC_FONT=NanumGothic  # 한글 폰트 (배포시 설정)
```

## 개발 규칙

### 코드 스타일
- **Formatter**: Black (line-length=88)
- **Import 정렬**: isort
- **Type Hints**: 필수

### 새 변환기 추가
1. `services/converters/`에 클래스 생성
2. `BaseConverter` 상속
3. `ConverterFactory._converters`에 등록

## SuperClaude 사용

### 권장 페르소나
- `--architect`: 구조 설계
- `--code`: 구현
- `--debug`: 에러 해결
- `--security`: 보안 점검

### 작업 예시
```bash
# 변환기
/persona:code "MarkdownToPdfConverter 만들어줘"
/persona:code "한글 폰트 지원 추가해줘"

# API
/persona:code "변환 모드 파라미터 추가해줘"

# 보안
/persona:security "파일 업로드 검증 점검해줘"
```

## 실행 방법

### 시스템 의존성 설치

```bash
# Ubuntu
sudo apt install pandoc texlive-xetex fonts-nanum

# Mac
brew install pandoc
brew install --cask mactex  # 또는 basictex
```

### 로컬 실행

```bash
python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

uvicorn main:app --reload

# API 문서: http://localhost:8000/docs
```

### Docker

```bash
docker build -t pdfnmd-backend .
docker run -p 8000:8000 pdfnmd-backend
```

## 의존성

```txt
# requirements.txt

fastapi>=0.109.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.6
pydantic>=2.5.0
pydantic-settings>=2.1.0
aiofiles>=23.2.1
python-dotenv>=1.0.0

# PDF → MD
marker-pdf>=0.2.0

# MD → PDF
pypandoc>=1.12

# 개발용
black>=24.1.0
isort>=5.13.0
pytest>=7.4.0
pytest-asyncio>=0.23.0
httpx>=0.26.0
```

## Dockerfile

```dockerfile
FROM python:3.11-slim

# 시스템 의존성 (Pandoc, LaTeX, 한글 폰트)
RUN apt-get update && apt-get install -y \
    pandoc \
    texlive-xetex \
    texlive-fonts-recommended \
    fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads outputs

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 배포 고려사항

### EC2 사양
- **최소**: t3.medium (2 vCPU, 4GB RAM)
- **권장**: t3.large (2 vCPU, 8GB RAM)
- **GPU** (선택): g4dn.xlarge - PDF→MD 빠름

### 시스템 의존성
- **Pandoc**: MD→PDF 변환
- **XeLaTeX**: PDF 생성 (한글 지원)
- **한글 폰트**: NanumGothic 등

### 보안 체크리스트
- [ ] 파일 확장자 + MIME type 검증
- [ ] 파일 크기 제한
- [ ] CORS 설정
- [ ] 임시 파일 정리

## 참고 자료

- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [marker GitHub](https://github.com/VikParuchuri/marker)
- [Pandoc 문서](https://pandoc.org/)
- [pypandoc](https://github.com/JessicaTegworker/pypandoc)

## 메모

- marker 첫 실행시 모델 다운로드 (약 2GB)
- Pandoc + XeLaTeX 설치 필요 (Docker로 해결)
- 한글 PDF 출력시 폰트 설정 필수
- MD→PDF는 상대적으로 빠름, PDF→MD는 느림
