# PDFnMD Backend

PDF ↔ Markdown 양방향 변환 서비스의 FastAPI 백엔드입니다.

## 주요 기능

- **PDF → Markdown**: [marker](https://github.com/VikParuchuri/marker) 라이브러리를 사용한 고품질 변환 (테이블, 이미지 지원)
- **Markdown → PDF**: [Pandoc](https://pandoc.org/)을 사용한 깔끔한 PDF 생성 (한글 지원)
- **비동기 처리**: FastAPI BackgroundTasks를 활용한 백그라운드 변환
- **S3 이미지 업로드**: PDF 변환 시 이미지를 S3에 업로드하여 노션 붙여넣기 지원 (선택)
- **자동 정리**: 24시간 후 파일 자동 삭제

## 사용 제한

| 항목 | 제한 |
|------|------|
| 파일당 용량 | 최대 20MB |
| 동시 파일 수 | 최대 20개 |
| 총 용량 | 최대 100MB |
| 파일 보관 | 24시간 |

## 기술 스택

- **Framework**: FastAPI (Python 3.11+)
- **PDF → MD**: marker-pdf
- **MD → PDF**: pypandoc + XeLaTeX
- **검증**: Pydantic v2
- **ASGI 서버**: Uvicorn

## 빠른 시작

### 1. 시스템 의존성 설치

```bash
# Ubuntu/Debian
sudo apt install pandoc texlive-xetex fonts-nanum

# macOS
brew install pandoc
brew install --cask mactex  # 또는 basictex
```

### 2. 프로젝트 설정

```bash
# 저장소 클론
git clone <repository-url>
cd backend

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
```

### 3. 서버 실행

```bash
uvicorn main:app --reload
```

API 문서: http://localhost:8000/docs

## API 엔드포인트

### POST /api/convert
파일 변환 시작

```bash
# PDF → Markdown
curl -X POST "http://localhost:8000/api/convert" \
  -F "file=@document.pdf" \
  -F "mode=pdf-to-md"

# Markdown → PDF
curl -X POST "http://localhost:8000/api/convert" \
  -F "file=@document.md" \
  -F "mode=md-to-pdf"
```

**응답:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "mode": "pdf-to-md",
  "status": "processing",
  "message": "변환이 시작되었습니다"
}
```

### GET /api/status/{task_id}
변환 상태 조회

```bash
curl "http://localhost:8000/api/status/{task_id}"
```

**응답:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "mode": "pdf-to-md",
  "status": "completed",
  "progress": 100,
  "download_url": "/api/download/550e8400-e29b-41d4-a716-446655440000",
  "error": null,
  "filename": "document.pdf"
}
```

**상태 값:**
- `pending`: 대기 중
- `processing`: 변환 중
- `completed`: 완료
- `failed`: 실패

### GET /api/download/{task_id}
변환된 파일 다운로드

```bash
curl -O "http://localhost:8000/api/download/{task_id}"
```

### POST /api/download/batch
여러 파일 ZIP 다운로드

```bash
curl -X POST "http://localhost:8000/api/download/batch" \
  -H "Content-Type: application/json" \
  -d '{"task_ids": ["task_id_1", "task_id_2"]}'
```

### GET /health
헬스 체크

```bash
curl "http://localhost:8000/health"
```

## 프로젝트 구조

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py             # 의존성 주입
│   │   └── routes/
│   │       ├── convert.py      # 변환 API
│   │       ├── status.py       # 상태 조회 API
│   │       └── download.py     # 다운로드 API
│   │
│   ├── core/
│   │   ├── config.py           # 환경 설정
│   │   └── exceptions.py       # 커스텀 예외
│   │
│   ├── services/
│   │   ├── converters/
│   │   │   ├── base.py         # 추상 베이스 클래스
│   │   │   ├── pdf_to_md.py    # PDF→MD 변환기 (marker)
│   │   │   └── md_to_pdf.py    # MD→PDF 변환기 (Pandoc)
│   │   ├── converter_factory.py # 변환기 팩토리
│   │   ├── task_manager.py     # 작업 상태 관리
│   │   ├── file_manager.py     # 파일 저장/삭제/ZIP
│   │   └── s3_manager.py       # S3 이미지 업로드 (선택)
│   │
│   ├── models/
│   │   ├── types.py            # 공용 타입 정의
│   │   ├── request.py          # 요청 모델
│   │   └── response.py         # 응답 모델
│   │
│   └── utils/
│       └── file_validator.py   # 파일 검증 (시그니처, MIME)
│
├── uploads/                    # 업로드 임시 저장
├── outputs/                    # 변환 결과 저장
├── tests/
├── main.py                     # FastAPI 앱 진입점
├── requirements.txt
└── .env.example
```

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `ENV` | 실행 환경 | `development` |
| `HOST` | 서버 호스트 | `0.0.0.0` |
| `PORT` | 서버 포트 | `8000` |
| `ALLOWED_ORIGINS` | CORS 허용 출처 | `http://localhost:5173` |
| `MAX_FILE_SIZE_MB` | 최대 파일 크기 | `20` |
| `MAX_FILES` | 최대 파일 수 | `20` |
| `MAX_TOTAL_SIZE_MB` | 최대 총 용량 | `100` |
| `UPLOAD_DIR` | 업로드 디렉토리 | `./uploads` |
| `OUTPUT_DIR` | 출력 디렉토리 | `./outputs` |
| `FILE_RETENTION_HOURS` | 파일 보관 시간 | `24` |
| `AWS_ACCESS_KEY_ID` | AWS 액세스 키 (선택) | - |
| `AWS_SECRET_ACCESS_KEY` | AWS 시크릿 키 (선택) | - |
| `AWS_BUCKET_NAME` | S3 버킷 이름 (선택) | - |
| `AWS_REGION` | AWS 리전 | `ap-northeast-2` |
| `MARKER_USE_GPU` | marker GPU 사용 | `false` |
| `PANDOC_PDF_ENGINE` | PDF 엔진 | `xelatex` |

## 아키텍처

### 변환기 팩토리 패턴

```python
from app.services import ConverterFactory

# 변환기 가져오기
converter = ConverterFactory.get_converter("pdf-to-md")

# 변환 실행
output_path = await converter.convert(input_path, output_dir)
```

### 작업 관리

```python
from app.services import task_manager

# 작업 생성
task = task_manager.create_task(
    mode="pdf-to-md",
    original_filename="document.pdf",
    input_path=saved_path
)

# 상태 업데이트
task_manager.update_task(task.task_id, status="completed", progress=100)

# 작업 조회
task = task_manager.get_task(task_id)
```

## 보안 기능

- **Path Traversal 방지**: 파일명 검증 및 경로 정규화 (uploads 디렉토리 제한)
- **파일 시그니처 검증**: PDF 매직 바이트(`%PDF`) 및 텍스트 파일 검증
- **심볼릭 링크 검증**: 경로 탈출 방지를 위한 resolved 경로 확인
- **보안 헤더**: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
- **CORS 제한**: 허용된 출처만 접근 가능
- **프로덕션 보안**: HSTS 헤더, API 문서 비활성화, 에러 메시지 숨김

## 개발

### 코드 스타일

```bash
# 포맷팅
black .
isort .
```

### 테스트

```bash
pytest
```

### 새 변환기 추가

1. `app/services/converters/`에 클래스 생성
2. `BaseConverter` 상속 및 필수 메서드 구현
3. `ConverterFactory._converters`에 등록

```python
# app/services/converters/new_converter.py
from pathlib import Path
from .base import BaseConverter

class NewConverter(BaseConverter):
    @property
    def input_extension(self) -> str:
        return '.input'

    @property
    def output_extension(self) -> str:
        return '.output'

    @property
    def mode(self) -> str:
        return 'input-to-output'

    def _convert_sync(self, input_path: Path, output_path: Path) -> None:
        # 동기 변환 로직 구현
        pass
```

4. `converter_factory.py`에 등록:
```python
_converters: Dict[ConversionMode, Type[BaseConverter]] = {
    "pdf-to-md": PdfToMarkdownConverter,
    "md-to-pdf": MarkdownToPdfConverter,
    "input-to-output": NewConverter,  # 추가
}
```

## Docker

```bash
# 빌드
docker build -t pdfnmd-backend .

# 실행
docker run -p 8000:8000 pdfnmd-backend
```

## 에러 코드

| HTTP 상태 | 설명 |
|-----------|------|
| 400 | 잘못된 파일 타입, 파일 수 초과 |
| 404 | 작업을 찾을 수 없음 (만료 또는 존재하지 않음) |
| 413 | 파일 크기 초과 |
| 500 | 변환 실패 또는 서버 오류 |

## 주의사항

- **marker 모델**: 첫 실행 시 약 2GB 모델 다운로드 필요
- **한글 PDF 생성**: XeLaTeX와 한글 폰트(NanumGothic 등) 필수
- **파일 보관**: 24시간 후 자동 삭제 (설정 변경 가능)
- **S3 설정**: AWS 환경변수 설정 시 PDF 이미지가 S3에 업로드됨 (노션 붙여넣기 지원)
- **동시성**: 싱글톤 패턴 및 스레드 안전 잠금 적용

## 라이선스

MIT License
