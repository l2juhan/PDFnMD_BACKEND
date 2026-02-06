# CLAUDE.md - PDFnMD Backend

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

**PDFnMD** - PDF → GFM(GitHub Flavored Markdown) 변환 무료 웹 서비스 백엔드

### 핵심 기능
- **PDF → GFM 변환**: marker-pdf 라이브러리 (AI 기반 고품질 변환)
- **이미지 처리**: Cloudflare R2 영구 저장 (S3 호환 API)
- **비동기 처리**: FastAPI BackgroundTasks 기반

### 제한 사항
| 항목 | 제한값 |
|------|--------|
| 파일당 최대 크기 | 20MB |
| 동시 업로드 파일 수 | 1개 |
| 파일 보관 기간 | 24시간 (R2 이미지는 영구) |

## 기술 스택

| 분류 | 기술 | 용도 |
|------|------|------|
| Framework | FastAPI | REST API 서버 |
| ASGI Server | Uvicorn | 비동기 서버 |
| PDF 변환 | marker-pdf | AI 기반 고품질 PDF 파싱 |
| 데이터 검증 | Pydantic v2 | 요청/응답 모델 |
| 클라우드 스토리지 | boto3 | Cloudflare R2 (S3 호환) |

## 프로젝트 구조

```text
backend/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── convert.py       # POST /api/convert
│   │       ├── status.py        # GET /api/status/{task_id}
│   │       ├── content.py       # GET /api/content/{task_id}
│   │       └── download.py      # GET /api/download/{task_id}
│   │
│   ├── core/
│   │   ├── config.py            # 환경 설정 (Pydantic Settings)
│   │   └── exceptions.py        # 커스텀 예외 클래스
│   │
│   ├── services/
│   │   ├── converters/
│   │   │   ├── base.py          # 추상 베이스 클래스 (BaseConverter)
│   │   │   └── pdf_to_md.py     # PDF→GFM 변환기 (marker-pdf)
│   │   ├── converter_factory.py # 변환기 팩토리 패턴
│   │   ├── task_manager.py      # 작업 상태 관리 (메모리 기반)
│   │   ├── file_manager.py      # 파일 저장/삭제
│   │   └── s3_manager.py        # Cloudflare R2 업로드
│   │
│   ├── models/
│   │   ├── types.py             # 공용 타입 정의 (ConversionMode, TaskStatus)
│   │   ├── request.py           # 요청 모델
│   │   └── response.py          # 응답 모델
│   │
│   └── utils/
│       └── file_validator.py    # PDF 파일 검증 (시그니처)
│
├── uploads/                     # 업로드 임시 저장 (24시간)
├── outputs/                     # 변환 결과 저장 (24시간)
├── tests/
├── main.py                      # FastAPI 앱 진입점
├── requirements.txt
└── .env.example
```

## API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| `POST` | `/api/convert` | PDF 변환 시작 (단일 파일) |
| `GET` | `/api/status/{task_id}` | 변환 상태 조회 |
| `GET` | `/api/content/{task_id}` | 변환된 GFM 콘텐츠 조회 (클립보드용) |
| `GET` | `/api/download/{task_id}` | 변환된 파일 다운로드 |
| `GET` | `/health` | 헬스 체크 |

### 변환 모드
- `pdf-to-md`: PDF → GFM 변환 (유일하게 지원되는 모드)

### 작업 상태 (TaskStatus)
- `pending`: 대기 중
- `processing`: 변환 중
- `completed`: 완료
- `failed`: 실패

## 아키텍처 패턴

### 변환기 팩토리 패턴
```python
ConverterFactory.get_converter(mode) → BaseConverter → convert()
```
- 새로운 변환 형식 추가 시 확장 용이
- 변환기별 독립적인 구현 및 테스트 가능

### 작업 흐름
1. `POST /api/convert` → 파일 저장 → Task 생성 → BackgroundTask 시작
2. 클라이언트가 `GET /api/status/{task_id}` 폴링 (2초 간격)
3. 완료 시 `GET /api/content/{task_id}`로 GFM 콘텐츠 조회

### 싱글톤 서비스
- `task_manager`: 작업 상태 관리 (메모리 기반, 스레드 안전)
- `file_manager`: 파일 저장/삭제
- `s3_manager` → `r2_manager`: Cloudflare R2 이미지 영구 저장

## 개발 명령어

```bash
# 가상환경 설정
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# 서버 실행 (개발 모드)
uvicorn main:app --reload --port 8000

# 포맷팅
black .
isort .

# 테스트
pytest
pytest tests/test_convert.py -v
pytest tests/test_convert.py::test_function_name -v
```

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `ENV` | 실행 환경 (development/production) | `development` |
| `HOST` | 서버 호스트 | `0.0.0.0` |
| `PORT` | 서버 포트 | `8000` |
| `ALLOWED_ORIGINS` | CORS 허용 출처 | `http://localhost:5173` |
| `MAX_FILE_SIZE_MB` | 최대 파일 크기 | `20` |
| `FILE_RETENTION_HOURS` | 파일 보관 시간 | `24` |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 액세스 키 | - |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 시크릿 키 | - |
| `R2_BUCKET_NAME` | R2 버킷 이름 | - |
| `R2_ENDPOINT_URL` | R2 엔드포인트 URL | - |
| `R2_PUBLIC_URL` | R2 퍼블릭 URL (이미지 접근용) | - |
| `MARKER_USE_GPU` | marker GPU 사용 | `false` |

## 새 변환기 추가

1. `app/services/converters/`에 클래스 생성 (`BaseConverter` 상속)
2. 필수 구현: `input_extension`, `output_extension`, `mode`, `_convert_sync()`
3. `converter_factory.py`의 `_converters` dict에 등록
4. `app/models/types.py`의 `ConversionMode`에 새 모드 추가

```python
# 예시: app/services/converters/new_converter.py
from pathlib import Path
from .base import BaseConverter

class NewConverter(BaseConverter):
    @property
    def input_extension(self) -> str:
        return ".new"

    @property
    def output_extension(self) -> str:
        return ".out"

    @property
    def mode(self) -> str:
        return "new-to-out"

    def _convert_sync(self, input_path: Path, output_path: Path, task_id: str | None = None) -> None:
        # 변환 로직 구현
        pass
```

```python
# app/models/types.py 수정
ConversionMode = Literal["pdf-to-md", "new-to-out"]
```

## 보안 요구사항

- **Path Traversal 방지**: 파일명 검증 및 경로 정규화 (uploads 디렉토리 제한)
- **파일 시그니처 검증**: PDF 매직 바이트 (`%PDF`) 검증
- **심볼릭 링크 검증**: 경로 탈출 방지를 위한 resolved 경로 확인
- **CORS 제한**: 허용된 출처만 접근 가능
- **보안 헤더**: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
- **프로덕션 추가 보안**: HSTS 헤더, API 문서 비활성화, 에러 메시지 숨김

## 코드 스타일

- **Formatter**: Black (line-length=88)
- **Import 정렬**: isort
- **Type Hints**: 필수
- **언어**: 한국어 주석 허용

## GitHub 템플릿 규칙

**중요**: Issue나 PR 생성 시 반드시 `.github/` 폴더의 템플릿을 따를 것

### PR 템플릿 (`.github/PULL_REQUEST_TEMPLATE.md`)
```
## Issue number and Link
closed #이슈번호

## Summary
## Changes
## PR Type (Feature/Bugfix/Refactoring 등)
## Screenshot
```

### Issue 템플릿
- **버그**: `.github/ISSUE_TEMPLATE/bug-report-template.md` - 제목: `[Bug] 설명`
- **기능 요청**: `.github/ISSUE_TEMPLATE/feature-request-template.md` - 제목: `[Feat] 설명`

## 주의사항

- marker 첫 실행 시 약 2GB 모델 자동 다운로드
- 메모리 기반 TaskManager로 서버 재시작 시 작업 정보 소실
- 단일 파일 업로드만 지원 (다중 파일 업로드 미지원)
- **단방향 변환만 지원**: PDF → GFM만 지원 (MD → PDF 기능 제거됨)

## 배포 환경

### AWS EC2 권장 사양
| 환경 | 인스턴스 | vCPU | RAM | 스토리지 |
|------|----------|------|-----|----------|
| 개발 | t3.medium | 2 | 4GB | 30GB EBS |
| 프로덕션 | t3.large | 2 | 8GB | 50GB EBS |

### 배포 구성
- OS: Ubuntu 22.04 LTS
- 리버스 프록시: Nginx
- SSL: Let's Encrypt (certbot)
- 프로세스 관리: systemd

## 참고 자료

- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [marker-pdf GitHub](https://github.com/VikParuchuri/marker)
- [Cloudflare R2](https://developers.cloudflare.com/r2/)
- PRD.md - 제품 요구사항 문서
- SRS.md - 소프트웨어 요구사항 명세서

## Git 커밋 규칙

### Co-Authored-By 제외
이 프로젝트에서는 커밋 메시지에 `Co-Authored-By` 라인을 포함하지 않습니다.