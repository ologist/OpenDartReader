# -*- coding: utf-8 -*-
# test_api.py — FastAPI 엔드포인트 단위 테스트
#
# httpx의 TestClient 대신 fastapi.testclient.TestClient를 사용한다.
# MCP 라이프사이클(lifespan) 의존성을 우회하기 위해 app을 직접 import하지 않고
# 엔드포인트 함수들을 모킹된 환경에서 테스트한다.

import os
import sys
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import FAKE_API_KEY, SAMPLE_CORPS, SAMPLE_FINSTATE_RECORDS


# ── FastAPI TestClient 픽스처 ─────────────────────────────────────────────────

@pytest.fixture(scope='module')
def client(tmp_path_factory):
    """
    DART_API_KEY 환경변수와 OpenDartReader 초기화를 mock으로 우회하여
    FastAPI TestClient를 반환한다.
    MCP lifespan은 asynccontextmanager mock으로 단순화한다.
    """
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    tmp_path = tmp_path_factory.mktemp('api_test')
    original_cwd = os.getcwd()
    os.chdir(tmp_path)

    corp_codes_df = pd.DataFrame(SAMPLE_CORPS)

    # lifespan을 no-op으로 교체
    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    with patch.dict(os.environ, {'DART_API_KEY': FAKE_API_KEY}):
        with patch('opendart_mcp.dart_list.corp_codes', return_value=corp_codes_df):
            # mcp.server.fastmcp.FastMCP import 전에 session_manager를 mock
            mock_mcp = MagicMock()
            mock_mcp.session_manager.run.return_value.__aenter__ = AsyncMock(return_value=None)
            mock_mcp.session_manager.run.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_mcp.tool.return_value = lambda f: f
            mock_mcp.streamable_http_app.return_value = MagicMock()

            with patch('mcp.server.fastmcp.FastMCP', return_value=mock_mcp):
                import importlib
                import app.main as main_module
                importlib.reload(main_module)

                # lifespan override
                main_module.app.router.lifespan_context = _noop_lifespan

                from fastapi.testclient import TestClient
                test_client = TestClient(main_module.app, raise_server_exceptions=False)

    os.chdir(original_cwd)
    return test_client, main_module


# ── /health 엔드포인트 테스트 ─────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        """헬스체크 엔드포인트가 200을 반환한다."""
        tc, _ = client
        response = tc.get('/health')
        assert response.status_code == 200

    def test_health_returns_status_ok(self, client):
        """헬스체크 응답에 status: ok가 포함된다."""
        tc, _ = client
        response = tc.get('/health')
        assert response.json()['status'] == 'ok'

    def test_health_reflects_api_key_set_true_when_key_present(self, client):
        """DART_API_KEY가 설정되어 있으면 dart_api_key_set이 true이다."""
        tc, _ = client
        response = tc.get('/health')
        assert response.json()['dart_api_key_set'] is True

    def test_health_reflects_api_key_set_false_when_key_missing(self, tmp_path):
        """DART_API_KEY가 없으면 dart_api_key_set이 false이다."""
        from contextlib import asynccontextmanager
        from unittest.mock import AsyncMock

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        @asynccontextmanager
        async def _noop_lifespan(app):
            yield

        corp_codes_df = pd.DataFrame(SAMPLE_CORPS)

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('DART_API_KEY', None)
            with patch('opendart_mcp.dart_list.corp_codes', return_value=corp_codes_df):
                mock_mcp = MagicMock()
                mock_mcp.session_manager.run.return_value.__aenter__ = AsyncMock(return_value=None)
                mock_mcp.session_manager.run.return_value.__aexit__ = AsyncMock(return_value=None)
                mock_mcp.tool.return_value = lambda f: f
                mock_mcp.streamable_http_app.return_value = MagicMock()

                with patch('mcp.server.fastmcp.FastMCP', return_value=mock_mcp):
                    import importlib
                    import app.main as main_module
                    importlib.reload(main_module)
                    main_module.app.router.lifespan_context = _noop_lifespan

                    from fastapi.testclient import TestClient
                    tc = TestClient(main_module.app, raise_server_exceptions=False)
                    response = tc.get('/health')

        os.chdir(original_cwd)
        assert response.json()['dart_api_key_set'] is False


# ── /list 엔드포인트 테스트 ───────────────────────────────────────────────────

class TestListEndpoint:
    def test_list_returns_200_with_records(self, client):
        """/list가 정상 응답 시 200을 반환하고 레코드 목록을 포함한다."""
        tc, mod = client
        records = [{'rcept_no': '001', 'corp_name': '삼성전자'}]
        mock_reader = MagicMock()
        mock_reader.list.return_value = pd.DataFrame(records)

        with patch.object(mod, '_get_dart_http', return_value=mock_reader):
            response = tc.get('/list')

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_returns_empty_list_when_no_disclosures(self, client):
        """/list 결과가 없으면 빈 배열을 반환한다."""
        tc, mod = client
        mock_reader = MagicMock()
        mock_reader.list.return_value = pd.DataFrame()

        with patch.object(mod, '_get_dart_http', return_value=mock_reader):
            response = tc.get('/list')

        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_404_for_unknown_corp(self, client):
        """/list에서 존재하지 않는 corp 파라미터는 404를 반환한다."""
        tc, mod = client
        mock_reader = MagicMock()
        mock_reader.list.side_effect = ValueError('could not find "없는회사"')

        with patch.object(mod, '_get_dart_http', return_value=mock_reader):
            response = tc.get('/list', params={'corp': '없는회사'})

        assert response.status_code == 404

    def test_list_passes_corp_param_to_dart_reader(self, client):
        """/list?corp=삼성전자가 dart.list(corp='삼성전자')를 호출한다."""
        tc, mod = client
        mock_reader = MagicMock()
        mock_reader.list.return_value = pd.DataFrame()

        with patch.object(mod, '_get_dart_http', return_value=mock_reader):
            tc.get('/list', params={'corp': '삼성전자'})

        mock_reader.list.assert_called_once()
        call_kwargs = mock_reader.list.call_args[1]
        assert call_kwargs['corp'] == '삼성전자'


# ── /company/{corp} 엔드포인트 테스트 ────────────────────────────────────────

class TestCompanyEndpoint:
    def test_company_returns_200_with_company_data(self, client):
        """/company/{corp}가 회사 정보를 포함한 200 응답을 반환한다."""
        tc, mod = client
        company_data = {
            'status': '000',
            'corp_code': '00126380',
            'corp_name': '삼성전자',
            'stock_code': '005930',
        }
        mock_reader = MagicMock()
        mock_reader.company.return_value = company_data

        with patch.object(mod, '_get_dart_http', return_value=mock_reader):
            response = tc.get('/company/005930')

        assert response.status_code == 200
        assert response.json()['corp_name'] == '삼성전자'

    def test_company_passes_corp_to_dart_reader(self, client):
        """/company/{corp}가 dart.company(corp)를 올바른 인자로 호출한다."""
        tc, mod = client
        mock_reader = MagicMock()
        mock_reader.company.return_value = {'status': '000'}

        with patch.object(mod, '_get_dart_http', return_value=mock_reader):
            tc.get('/company/삼성전자')

        mock_reader.company.assert_called_once_with('삼성전자')


# ── /corp_code/{corp} 엔드포인트 테스트 ──────────────────────────────────────

class TestCorpCodeEndpoint:
    def test_corp_code_returns_200_with_code(self, client):
        """/corp_code/{corp}가 고유번호를 포함한 200 응답을 반환한다."""
        tc, mod = client
        mock_reader = MagicMock()
        mock_reader.find_corp_code.return_value = '00126380'

        with patch.object(mod, '_get_dart_http', return_value=mock_reader):
            response = tc.get('/corp_code/삼성전자')

        assert response.status_code == 200
        assert response.json()['corp_code'] == '00126380'

    def test_corp_code_returns_404_when_not_found(self, client):
        """/corp_code/{corp}에서 고유번호가 없으면 404를 반환한다."""
        tc, mod = client
        mock_reader = MagicMock()
        mock_reader.find_corp_code.return_value = None

        with patch.object(mod, '_get_dart_http', return_value=mock_reader):
            response = tc.get('/corp_code/없는회사')

        assert response.status_code == 404
