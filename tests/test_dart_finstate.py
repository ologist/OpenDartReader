# -*- coding: utf-8 -*-
# test_dart_finstate.py — dart_finstate 모듈 단위 테스트

import os
import sys
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opendart_mcp import dart_finstate
from tests.conftest import (
    FAKE_API_KEY,
    SAMPLE_FINSTATE_RECORDS,
    make_finstate_response,
    make_finstate_empty_response,
)


# ── finstate() 단일 회사 테스트 ───────────────────────────────────────────────

class TestFinstateSingle:
    def test_returns_dataframe_for_single_corp(self):
        """단일 회사 재무정보 정상 응답을 DataFrame으로 반환한다."""
        with patch('requests.get', return_value=make_finstate_response()):
            df = dart_finstate.finstate(FAKE_API_KEY, '00126380', 2023)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_requests_single_account_endpoint_for_single_corp(self):
        """단일 corp_code이면 fnlttSinglAcnt.json 엔드포인트로 요청한다."""
        with patch('requests.get', return_value=make_finstate_response()) as mock_get:
            dart_finstate.finstate(FAKE_API_KEY, '00126380', 2023)
        call_url = mock_get.call_args[0][0]
        assert 'fnlttSinglAcnt.json' in call_url

    def test_requests_multi_account_endpoint_for_multiple_corps(self):
        """쉼표로 구분된 corp_code이면 fnlttMultiAcnt.json 엔드포인트로 요청한다."""
        with patch('requests.get', return_value=make_finstate_response()) as mock_get:
            dart_finstate.finstate(FAKE_API_KEY, '00126380,00164779', 2023)
        call_url = mock_get.call_args[0][0]
        assert 'fnlttMultiAcnt.json' in call_url

    def test_returns_empty_dataframe_when_no_list_key(self):
        """응답에 list 키가 없으면 빈 DataFrame을 반환한다."""
        with patch('requests.get', return_value=make_finstate_empty_response()):
            df = dart_finstate.finstate(FAKE_API_KEY, '00126380', 2023)
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_corp_code_in_request_params(self):
        """corp_code가 요청 파라미터에 포함된다."""
        with patch('requests.get', return_value=make_finstate_response()) as mock_get:
            dart_finstate.finstate(FAKE_API_KEY, '00126380', 2023)
        call_params = mock_get.call_args[1]['params']
        assert call_params['corp_code'] == '00126380'

    def test_bsns_year_in_request_params(self):
        """사업연도가 요청 파라미터에 포함된다."""
        with patch('requests.get', return_value=make_finstate_response()) as mock_get:
            dart_finstate.finstate(FAKE_API_KEY, '00126380', 2023)
        call_params = mock_get.call_args[1]['params']
        assert call_params['bsns_year'] == 2023

    def test_reprt_code_defaults_to_annual_report(self):
        """reprt_code 기본값이 사업보고서 코드(11011)이다."""
        with patch('requests.get', return_value=make_finstate_response()) as mock_get:
            dart_finstate.finstate(FAKE_API_KEY, '00126380', 2023)
        call_params = mock_get.call_args[1]['params']
        assert call_params['reprt_code'] == '11011'

    def test_dataframe_has_expected_columns(self):
        """반환된 DataFrame에 account_nm, thstrm_amount 등 핵심 컬럼이 있다."""
        with patch('requests.get', return_value=make_finstate_response()):
            df = dart_finstate.finstate(FAKE_API_KEY, '00126380', 2023)
        assert 'account_nm' in df.columns
        assert 'thstrm_amount' in df.columns


# ── finstate() 다중 회사 테스트 ───────────────────────────────────────────────

class TestFinStateMulti:
    def test_returns_dataframe_for_multiple_corps(self):
        """다중 회사 재무정보 응답도 DataFrame으로 반환한다."""
        multi_records = [
            {**SAMPLE_FINSTATE_RECORDS[0], 'corp_code': '00126380'},
            {**SAMPLE_FINSTATE_RECORDS[0], 'corp_code': '00164779'},
        ]
        with patch('requests.get', return_value=make_finstate_response(multi_records)):
            df = dart_finstate.finstate(FAKE_API_KEY, '00126380,00164779', 2023)
        assert len(df) == 2

    def test_returns_empty_dataframe_when_multi_has_no_list(self):
        """다중 회사 응답에 list 키가 없으면 빈 DataFrame을 반환한다."""
        with patch('requests.get', return_value=make_finstate_empty_response()):
            df = dart_finstate.finstate(FAKE_API_KEY, '00126380,00164779', 2023)
        assert df.empty


# ── finstate_all() 테스트 ─────────────────────────────────────────────────────

class TestFinStateAll:
    def test_returns_dataframe_on_successful_response(self):
        """전체 재무제표 정상 응답을 DataFrame으로 반환한다."""
        with patch('requests.get', return_value=make_finstate_response()):
            df = dart_finstate.finstate_all(FAKE_API_KEY, '00126380', 2023)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_returns_empty_dataframe_when_no_list_key(self):
        """응답에 list 키가 없으면 빈 DataFrame을 반환한다."""
        with patch('requests.get', return_value=make_finstate_empty_response()):
            df = dart_finstate.finstate_all(FAKE_API_KEY, '00126380', 2023)
        assert df.empty

    def test_fs_div_param_is_passed_correctly(self):
        """fs_div 파라미터가 요청에 올바르게 포함된다."""
        with patch('requests.get', return_value=make_finstate_response()) as mock_get:
            dart_finstate.finstate_all(FAKE_API_KEY, '00126380', 2023, fs_div='OFS')
        call_params = mock_get.call_args[1]['params']
        assert call_params['fs_div'] == 'OFS'

    def test_requests_single_all_endpoint(self):
        """fnlttSinglAcntAll.json 엔드포인트로 요청한다."""
        with patch('requests.get', return_value=make_finstate_response()) as mock_get:
            dart_finstate.finstate_all(FAKE_API_KEY, '00126380', 2023)
        call_url = mock_get.call_args[0][0]
        assert 'fnlttSinglAcntAll.json' in call_url

    def test_reprt_code_passed_correctly(self):
        """reprt_code 파라미터가 요청에 올바르게 포함된다."""
        with patch('requests.get', return_value=make_finstate_response()) as mock_get:
            dart_finstate.finstate_all(FAKE_API_KEY, '00126380', 2023, reprt_code='11012')
        call_params = mock_get.call_args[1]['params']
        assert call_params['reprt_code'] == '11012'
