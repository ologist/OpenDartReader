# -*- coding: utf-8 -*-
# test_dart_list.py — dart_list 모듈 단위 테스트

import os
import sys
import io
import zipfile
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opendart_mcp import dart_list
from tests.conftest import (
    FAKE_API_KEY,
    SAMPLE_CORPS,
    make_list_response,
    make_empty_list_response,
    make_error_response,
    make_corp_codes_zip,
)


# ── list() 테스트 ─────────────────────────────────────────────────────────────

class TestList:
    def test_returns_dataframe_on_successful_response(self):
        """정상 응답이면 공시 목록을 DataFrame으로 반환한다."""
        records = [
            {'rcept_no': '20240101000001', 'corp_name': '삼성전자', 'report_nm': '사업보고서'},
        ]
        with patch('requests.get', return_value=make_list_response(records)):
            df = dart_list.list(FAKE_API_KEY)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]['corp_name'] == '삼성전자'

    def test_returns_empty_dataframe_when_no_list_key(self):
        """응답에 list 키가 없으면 빈 DataFrame을 반환한다."""
        with patch('requests.get', return_value=make_empty_list_response()):
            df = dart_list.list(FAKE_API_KEY)
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_paging_fetches_all_pages(self):
        """total_page > 1이면 모든 페이지를 가져와 하나의 DataFrame으로 합친다."""
        page1_records = [{'rcept_no': '001', 'corp_name': '삼성전자'}]
        page2_records = [{'rcept_no': '002', 'corp_name': 'SK하이닉스'}]

        # 첫 번째 호출: total_page=2, 두 번째 호출: 두 번째 페이지
        page1_resp = make_list_response(page1_records, total_page=2)
        page2_resp = MagicMock()
        page2_resp.json.return_value = {
            'status': '000',
            'total_page': 2,
            'list': page2_records,
        }
        page2_resp.content = b'not-xml'

        with patch('requests.get', side_effect=[page1_resp, page2_resp]):
            df = dart_list.list(FAKE_API_KEY)

        assert len(df) == 2
        assert set(df['rcept_no']) == {'001', '002'}

    def test_passes_corp_code_in_request_params(self):
        """corp_code 인자가 HTTP 요청 params에 포함된다."""
        with patch('requests.get', return_value=make_empty_list_response()) as mock_get:
            dart_list.list(FAKE_API_KEY, corp_code='00126380')
        call_params = mock_get.call_args[1]['params']
        assert call_params['corp_code'] == '00126380'

    def test_passes_final_flag_as_Y_when_true(self):
        """final=True이면 last_reprt_at 파라미터가 'Y'로 전달된다."""
        with patch('requests.get', return_value=make_empty_list_response()) as mock_get:
            dart_list.list(FAKE_API_KEY, final=True)
        call_params = mock_get.call_args[1]['params']
        assert call_params['last_reprt_at'] == 'Y'

    def test_passes_final_flag_as_N_when_false(self):
        """final=False이면 last_reprt_at 파라미터가 'N'으로 전달된다."""
        with patch('requests.get', return_value=make_empty_list_response()) as mock_get:
            dart_list.list(FAKE_API_KEY, final=False)
        call_params = mock_get.call_args[1]['params']
        assert call_params['last_reprt_at'] == 'N'

    def test_kind_param_included_when_provided(self):
        """kind 인자가 제공되면 pblntf_ty 파라미터로 전달된다."""
        with patch('requests.get', return_value=make_empty_list_response()) as mock_get:
            dart_list.list(FAKE_API_KEY, kind='A')
        call_params = mock_get.call_args[1]['params']
        assert call_params['pblntf_ty'] == 'A'

    def test_kind_param_not_included_when_empty(self):
        """kind가 빈 문자열이면 pblntf_ty 파라미터가 포함되지 않는다."""
        with patch('requests.get', return_value=make_empty_list_response()) as mock_get:
            dart_list.list(FAKE_API_KEY, kind='')
        call_params = mock_get.call_args[1]['params']
        assert 'pblntf_ty' not in call_params


# ── corp_codes() 테스트 ───────────────────────────────────────────────────────

class TestCorpCodes:
    def test_returns_dataframe_from_xml_zip(self):
        """ZIP 안의 CORPCODE.xml을 파싱하여 DataFrame을 반환한다."""
        zip_bytes = make_corp_codes_zip(SAMPLE_CORPS)
        mock_resp = MagicMock()
        mock_resp.content = zip_bytes

        with patch('requests.get', return_value=mock_resp):
            df = dart_list.corp_codes(FAKE_API_KEY)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(SAMPLE_CORPS)

    def test_returned_dataframe_has_corp_code_column(self):
        """반환된 DataFrame에 corp_code 컬럼이 있다."""
        zip_bytes = make_corp_codes_zip(SAMPLE_CORPS)
        mock_resp = MagicMock()
        mock_resp.content = zip_bytes

        with patch('requests.get', return_value=mock_resp):
            df = dart_list.corp_codes(FAKE_API_KEY)

        assert 'corp_code' in df.columns

    def test_returned_dataframe_has_corp_name_column(self):
        """반환된 DataFrame에 corp_name 컬럼이 있다."""
        zip_bytes = make_corp_codes_zip(SAMPLE_CORPS)
        mock_resp = MagicMock()
        mock_resp.content = zip_bytes

        with patch('requests.get', return_value=mock_resp):
            df = dart_list.corp_codes(FAKE_API_KEY)

        assert 'corp_name' in df.columns

    def test_corp_names_match_input_data(self):
        """파싱된 회사명이 입력 XML 데이터와 일치한다."""
        zip_bytes = make_corp_codes_zip(SAMPLE_CORPS)
        mock_resp = MagicMock()
        mock_resp.content = zip_bytes

        with patch('requests.get', return_value=mock_resp):
            df = dart_list.corp_codes(FAKE_API_KEY)

        names = set(df['corp_name'].tolist())
        assert '삼성전자' in names
        assert 'SK하이닉스' in names

    def test_api_key_passed_in_request_params(self):
        """API 키가 crtfc_key 파라미터로 요청에 포함된다."""
        zip_bytes = make_corp_codes_zip()
        mock_resp = MagicMock()
        mock_resp.content = zip_bytes

        with patch('requests.get', return_value=mock_resp) as mock_get:
            dart_list.corp_codes(FAKE_API_KEY)

        call_params = mock_get.call_args[1]['params']
        assert call_params['crtfc_key'] == FAKE_API_KEY


# ── company() 테스트 ──────────────────────────────────────────────────────────

class TestCompany:
    def test_returns_dict_on_successful_response(self):
        """정상 응답이면 회사 정보를 dict로 반환한다."""
        company_data = {
            'status': '000',
            'corp_code': '00126380',
            'corp_name': '삼성전자',
            'stock_code': '005930',
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = company_data
        mock_resp.content = b'not-xml'

        with patch('requests.get', return_value=mock_resp):
            result = dart_list.company(FAKE_API_KEY, '00126380')

        assert result['corp_name'] == '삼성전자'

    def test_corp_code_passed_in_request_params(self):
        """corp_code가 요청 파라미터에 포함된다."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'status': '000'}
        mock_resp.content = b'not-xml'

        with patch('requests.get', return_value=mock_resp) as mock_get:
            dart_list.company(FAKE_API_KEY, '00126380')

        call_params = mock_get.call_args[1]['params']
        assert call_params['corp_code'] == '00126380'

    def test_requests_correct_endpoint(self):
        """company.json 엔드포인트로 요청한다."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'status': '000'}
        mock_resp.content = b'not-xml'

        with patch('requests.get', return_value=mock_resp) as mock_get:
            dart_list.company(FAKE_API_KEY, '00126380')

        call_url = mock_get.call_args[0][0]
        assert 'company.json' in call_url
