"""uv 마이그레이션 검증 테스트"""

import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# FastAPI 앱 임포트 테스트
from main import app


class TestUvMigration:
    """uv 마이그레이션 검증"""

    def test_python_version(self):
        """Python 버전 확인 (3.11+)"""
        assert sys.version_info >= (3, 11)

    def test_pyproject_exists(self):
        """pyproject.toml 존재 확인"""
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        assert pyproject.exists(), "pyproject.toml이 존재해야 합니다"

    def test_uv_lock_exists(self):
        """uv.lock 존재 확인"""
        uv_lock = Path(__file__).parent.parent / "uv.lock"
        assert uv_lock.exists(), "uv.lock이 존재해야 합니다"

    def test_requirements_removed(self):
        """requirements.txt 삭제 확인"""
        requirements = Path(__file__).parent.parent / "requirements.txt"
        assert not requirements.exists(), "requirements.txt가 삭제되어야 합니다"

    def test_old_venv_removed(self):
        """기존 venv 디렉토리 삭제 확인"""
        old_venv = Path(__file__).parent.parent / "venv"
        assert not old_venv.exists(), "venv/ 디렉토리가 삭제되어야 합니다"

    def test_new_venv_exists(self):
        """.venv 디렉토리 존재 확인 (uv 관리)"""
        new_venv = Path(__file__).parent.parent / ".venv"
        assert new_venv.exists(), ".venv/ 디렉토리가 존재해야 합니다"


class TestPackageImports:
    """핵심 패키지 임포트 테스트"""

    def test_fastapi_import(self):
        """FastAPI 임포트"""
        import fastapi
        assert fastapi.__version__

    def test_uvicorn_import(self):
        """Uvicorn 임포트"""
        import uvicorn
        assert uvicorn

    def test_pydantic_import(self):
        """Pydantic 임포트"""
        import pydantic
        assert pydantic.__version__

    def test_pydantic_settings_import(self):
        """Pydantic Settings 임포트"""
        import pydantic_settings
        assert pydantic_settings

    def test_boto3_import(self):
        """Boto3 임포트"""
        import boto3
        assert boto3.__version__

    def test_aiofiles_import(self):
        """Aiofiles 임포트"""
        import aiofiles
        assert aiofiles


class TestAppConfiguration:
    """앱 설정 테스트"""

    def test_app_instance(self):
        """FastAPI 앱 인스턴스 확인"""
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)

    def test_settings_load(self):
        """설정 로드 확인"""
        from app.core.config import settings
        assert settings.ENV in ("development", "production", "testing")

    def test_routes_registered(self):
        """라우트 등록 확인"""
        routes = [route.path for route in app.routes]
        assert "/health" in routes
        assert "/api/convert" in routes


@pytest.mark.asyncio
class TestHealthEndpoint:
    """헬스 엔드포인트 테스트"""

    async def test_health_check(self):
        """GET /health 응답 확인"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "healthy"}
