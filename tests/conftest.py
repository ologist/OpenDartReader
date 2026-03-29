# -*- coding: utf-8 -*-
# conftest.py — 공통 pytest 픽스처 정의
# 모든 테스트 파일에서 재사용하는 mock 데이터와 픽스처를 여기에 모은다.

import io
import zipfile
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest


# ── 공통 상수 ──────────────────────────────────────────────────────────────────

FAKE_API_KEY = 'test_api_key_0000000000000000000000'

# 샘플 회사 데이터: (corp_code, corp_name, stock_code)
SAMPLE_CORPS = [
    {'corp_code': '00126380', 'corp_name': '삼성전자', 'stock_code': '005930'},
    {'corp_code': '00164779', 'corp_name': 'SK하이닉스', 'stock_code': '000660'},
    {'corp_code': '00356361', 'corp_name': '카카오', 'stock_code': '035720'},
]


# ── corp_codes pickle 없이 OpenDartReader를 인스턴스화하는 픽스처 ──────────────

@pytest.fixture
def corp_codes_df():
    """테스트용 회사 고유번호 DataFrame."""
    return pd.DataFrame(SAMPLE_CORPS)


@pytest.fixture
def dart_reader(tmp_path, corp_codes_df):
    """
    외부 HTTP 요청 및 파일 I/O 없이 OpenDartReader 인스턴스를 생성한다.
    - dart_list.corp_codes() 호출을 mock 처리
    - 캐시 디렉토리를 tmp_path로 우회
    """
    import sys
    import os

    # OpenDartReader 패키지를 프로젝트 루트에서 임포트
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # 작업 디렉토리를 tmp_path로 변경하여 docs_cache를 임시 경로에 생성
    original_cwd = os.getcwd()
    os.chdir(tmp_path)

    try:
        with patch('opendart_mcp.dart_list.corp_codes', return_value=corp_codes_df):
            from opendart_mcp import OpenDartReader as ODR
            reader = ODR(FAKE_API_KEY)
    finally:
        os.chdir(original_cwd)

    return reader


# ── dart_list.list() 응답 mock 헬퍼 ───────────────────────────────────────────

def make_list_response(records: list, total_page: int = 1) -> MagicMock:
    """requests.get 응답 mock: list 엔드포인트용 JSON 구조."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        'status': '000',
        'message': '정상',
        'total_page': total_page,
        'list': records,
    }
    # content를 JSON 바이트로 설정해 ET.XML 파싱 실패 → except 분기 통과
    mock_resp.content = b'not-xml'
    return mock_resp


def make_empty_list_response() -> MagicMock:
    """결과가 없는 경우의 응답 mock."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        'status': '000',
        'message': '정상',
        'total_page': 1,
    }
    mock_resp.content = b'not-xml'
    return mock_resp


def make_error_response(status: str = '010', message: str = '등록되지 않은 키') -> MagicMock:
    """오류 상태 응답 mock."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'status': status, 'message': message}
    mock_resp.content = b'not-xml'
    mock_resp.text = f'{{"status": "{status}", "message": "{message}"}}'
    return mock_resp


# ── corp_codes ZIP+XML mock 헬퍼 ──────────────────────────────────────────────

def make_corp_codes_zip(corps: list = None) -> bytes:
    """
    dart_list.corp_codes()가 소비하는 ZIP+XML 바이트를 생성한다.
    corps: [{'corp_code': ..., 'corp_name': ..., 'stock_code': ...}, ...]
    """
    if corps is None:
        corps = SAMPLE_CORPS

    root = ET.Element('result')
    for c in corps:
        item = ET.SubElement(root, 'list')
        for key, val in c.items():
            child = ET.SubElement(item, key)
            child.text = val

    xml_bytes = ET.tostring(root, encoding='utf-8', xml_declaration=True)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('CORPCODE.xml', xml_bytes)
    return buf.getvalue()


# ── 재무정보 mock 헬퍼 ────────────────────────────────────────────────────────

SAMPLE_FINSTATE_RECORDS = [
    {
        'rcept_no': '20240101000001',
        'reprt_code': '11011',
        'bsns_year': '2023',
        'corp_code': '00126380',
        'sj_div': 'BS',
        'sj_nm': '재무상태표',
        'account_id': 'ifrs-full:Assets',
        'account_nm': '자산총계',
        'account_detail': '-',
        'thstrm_nm': '제 55 기',
        'thstrm_amount': '426206607000000',
        'frmtrm_nm': '제 54 기',
        'frmtrm_amount': '448375013000000',
        'ord': '1',
        'currency': 'KRW',
    }
]


def make_finstate_response(records=None) -> MagicMock:
    """재무정보 정상 응답 mock."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        'status': '000',
        'list': records if records is not None else SAMPLE_FINSTATE_RECORDS,
    }
    return mock_resp


def make_finstate_empty_response() -> MagicMock:
    """재무정보 빈 응답 mock (2015년 이전 등)."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'status': '000', 'message': '데이터 없음'}
    return mock_resp


# ── 이벤트 mock 헬퍼 ──────────────────────────────────────────────────────────

SAMPLE_EVENT_RECORDS = [
    {
        'rcept_no': '20240201000001',
        'corp_code': '00126380',
        'corp_name': '삼성전자',
        'report_nm': '유상증자결정',
        'rcept_dt': '20240201',
    }
]


def make_event_response(records=None) -> MagicMock:
    """이벤트 정상 응답 mock."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        'status': '000',
        'list': records if records is not None else SAMPLE_EVENT_RECORDS,
    }
    return mock_resp


def make_event_empty_response(status: str = '013') -> MagicMock:
    """이벤트 결과 없음 응답 mock."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'status': status, 'message': '데이터 없음'}
    return mock_resp
