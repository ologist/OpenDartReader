# -*- coding: utf-8 -*-
# test_dart.py — OpenDartReader 클래스 단위 테스트

import os
import sys
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import (
    FAKE_API_KEY,
    SAMPLE_CORPS,
    make_corp_codes_zip,
    make_list_response,
    make_finstate_response,
    make_finstate_empty_response,
    corp_codes_df,
)


# ── __init__ 테스트 ────────────────────────────────────────────────────────────

class TestOpenDartReaderInit:
    def test_api_key_is_stored_after_init(self, dart_reader):
        """초기화 후 api_key 속성이 올바르게 저장된다."""
        assert dart_reader.api_key == FAKE_API_KEY

    def test_corp_codes_is_dataframe_after_init(self, dart_reader):
        """초기화 후 corp_codes 속성이 DataFrame이다."""
        assert isinstance(dart_reader.corp_codes, pd.DataFrame)

    def test_corp_codes_contains_expected_columns(self, dart_reader):
        """corp_codes DataFrame에 corp_code, corp_name, stock_code 컬럼이 있다."""
        assert 'corp_code' in dart_reader.corp_codes.columns
        assert 'corp_name' in dart_reader.corp_codes.columns
        assert 'stock_code' in dart_reader.corp_codes.columns

    def test_cache_file_is_created_on_init(self, tmp_path):
        """초기화 시 docs_cache 디렉토리와 pkl 캐시 파일이 생성된다."""
        import glob
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch('opendart_mcp.dart_list.corp_codes', return_value=pd.DataFrame(SAMPLE_CORPS)):
                from opendart_mcp import OpenDartReader as ODR
                ODR(FAKE_API_KEY)
            cache_files = glob.glob(str(tmp_path / 'docs_cache' / 'opendart_mcp_corp_codes_*.pkl'))
            assert len(cache_files) == 1
        finally:
            os.chdir(original_cwd)

    def test_stale_cache_files_are_removed_on_init(self, tmp_path):
        """초기화 시 오늘 날짜가 아닌 이전 캐시 파일은 삭제된다."""
        import glob
        cache_dir = tmp_path / 'docs_cache'
        cache_dir.mkdir()
        stale_file = cache_dir / 'opendart_mcp_corp_codes_20200101.pkl'
        stale_file.write_bytes(b'stale')

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            with patch('opendart_mcp.dart_list.corp_codes', return_value=pd.DataFrame(SAMPLE_CORPS)):
                from opendart_mcp import OpenDartReader as ODR
                ODR(FAKE_API_KEY)
            assert not stale_file.exists(), "이전 날짜 캐시 파일이 삭제되어야 한다"
        finally:
            os.chdir(original_cwd)


# ── find_corp_code 테스트 ─────────────────────────────────────────────────────

class TestFindCorpCode:
    def test_returns_corp_code_by_company_name(self, dart_reader):
        """회사명으로 검색하면 올바른 고유번호를 반환한다."""
        result = dart_reader.find_corp_code('삼성전자')
        assert result == '00126380'

    def test_returns_corp_code_by_stock_code(self, dart_reader):
        """6자리 종목코드로 검색하면 올바른 고유번호를 반환한다."""
        result = dart_reader.find_corp_code('005930')
        assert result == '00126380'

    def test_returns_corp_code_by_corp_code_itself(self, dart_reader):
        """8자리 고유번호 자체로도 검색할 수 있다."""
        result = dart_reader.find_corp_code('00126380')
        assert result == '00126380'

    def test_returns_none_when_company_not_found(self, dart_reader):
        """존재하지 않는 회사명은 None을 반환한다."""
        result = dart_reader.find_corp_code('존재하지않는회사')
        assert result is None

    def test_returns_none_when_stock_code_not_found(self, dart_reader):
        """존재하지 않는 종목코드는 None을 반환한다."""
        result = dart_reader.find_corp_code('999999')
        assert result is None

    def test_returns_none_when_corp_code_not_found(self, dart_reader):
        """존재하지 않는 8자리 고유번호는 None을 반환한다."""
        result = dart_reader.find_corp_code('99999999')
        assert result is None

    def test_non_digit_string_searches_by_name(self, dart_reader):
        """숫자가 아닌 문자열은 회사명으로 검색한다."""
        result = dart_reader.find_corp_code('카카오')
        assert result == '00356361'

    def test_six_digit_string_searches_by_stock_code(self, dart_reader):
        """6자리 숫자는 종목코드로 검색한다."""
        result = dart_reader.find_corp_code('000660')
        assert result == '00164779'


# ── list() 테스트 ─────────────────────────────────────────────────────────────

class TestList:
    def test_raises_value_error_for_unknown_corp(self, dart_reader):
        """존재하지 않는 corp명으로 list() 호출 시 ValueError를 발생시킨다."""
        with pytest.raises(ValueError, match='could not find'):
            dart_reader.list(corp='없는회사')

    def test_calls_dart_list_with_empty_corp_code_when_corp_is_none(self, dart_reader):
        """corp=None이면 corp_code=''로 dart_list.list()를 호출한다."""
        with patch('opendart_mcp.dart_list.list', return_value=pd.DataFrame()) as mock_list:
            dart_reader.list()
            call_args = mock_list.call_args
            # 두 번째 인자(corp_code)가 빈 문자열
            assert call_args[0][1] == ''

    def test_calls_dart_list_with_resolved_corp_code(self, dart_reader):
        """유효한 corp명이면 고유번호로 변환하여 dart_list.list()를 호출한다."""
        with patch('opendart_mcp.dart_list.list', return_value=pd.DataFrame()) as mock_list:
            dart_reader.list(corp='삼성전자')
            call_args = mock_list.call_args
            assert call_args[0][1] == '00126380'


# ── finstate_all() 유효성 검사 테스트 ─────────────────────────────────────────

class TestFinStateAll:
    def test_raises_value_error_for_invalid_reprt_code(self, dart_reader):
        """잘못된 reprt_code를 전달하면 ValueError를 발생시킨다."""
        with pytest.raises(ValueError, match='invalid reprt_code'):
            dart_reader.finstate_all('삼성전자', 2023, reprt_code='99999')

    def test_raises_value_error_for_invalid_fs_div(self, dart_reader):
        """잘못된 fs_div를 전달하면 ValueError를 발생시킨다."""
        with pytest.raises(ValueError, match='invalid fs_div'):
            dart_reader.finstate_all('삼성전자', 2023, fs_div='INVALID')

    def test_raises_value_error_for_unknown_corp(self, dart_reader):
        """존재하지 않는 회사명으로 호출 시 ValueError를 발생시킨다."""
        with pytest.raises(ValueError, match='could not find'):
            dart_reader.finstate_all('없는회사', 2023)

    def test_valid_reprt_codes_do_not_raise(self, dart_reader):
        """올바른 reprt_code 값들은 ValueError를 발생시키지 않는다."""
        with patch('opendart_mcp.dart_finstate.finstate_all', return_value=pd.DataFrame()):
            for code in ['11013', '11012', '11014', '11011']:
                dart_reader.finstate_all('삼성전자', 2023, reprt_code=code)

    def test_valid_fs_div_values_do_not_raise(self, dart_reader):
        """올바른 fs_div 값들은 ValueError를 발생시키지 않는다."""
        with patch('opendart_mcp.dart_finstate.finstate_all', return_value=pd.DataFrame()):
            for div in ['CFS', 'OFS']:
                dart_reader.finstate_all('삼성전자', 2023, fs_div=div)

    def test_delegates_to_dart_finstate_with_correct_args(self, dart_reader):
        """올바른 인자가 dart_finstate.finstate_all()로 전달된다."""
        with patch('opendart_mcp.dart_finstate.finstate_all', return_value=pd.DataFrame()) as mock_fs:
            dart_reader.finstate_all('삼성전자', 2023, reprt_code='11011', fs_div='CFS')
            mock_fs.assert_called_once_with(
                FAKE_API_KEY, '00126380', 2023, reprt_code='11011', fs_div='CFS'
            )


# ── finstate() 테스트 ─────────────────────────────────────────────────────────

class TestFinState:
    def test_single_corp_resolved_to_corp_code(self, dart_reader):
        """단일 회사명은 고유번호로 변환하여 finstate()가 호출된다."""
        with patch('opendart_mcp.dart_finstate.finstate', return_value=pd.DataFrame()) as mock_fs:
            dart_reader.finstate('삼성전자', 2023)
            args = mock_fs.call_args[0]
            assert args[1] == '00126380'

    def test_multiple_corps_comma_separated(self, dart_reader):
        """쉼표로 구분된 여러 회사명은 각각 고유번호로 변환되어 전달된다."""
        with patch('opendart_mcp.dart_finstate.finstate', return_value=pd.DataFrame()) as mock_fs:
            dart_reader.finstate('삼성전자,SK하이닉스', 2023)
            args = mock_fs.call_args[0]
            assert '00126380' in args[1]
            assert '00164779' in args[1]


# ── event() 테스트 ────────────────────────────────────────────────────────────

class TestEvent:
    def test_raises_value_error_for_unknown_corp(self, dart_reader):
        """존재하지 않는 회사명으로 event() 호출 시 ValueError를 발생시킨다."""
        with pytest.raises(ValueError, match='could not find'):
            dart_reader.event('없는회사', '유상증자')

    def test_delegates_to_dart_event_with_resolved_corp_code(self, dart_reader):
        """유효한 회사명이면 고유번호로 변환하여 dart_event.event()를 호출한다."""
        with patch('opendart_mcp.dart_event.event', return_value=pd.DataFrame()) as mock_ev:
            dart_reader.event('삼성전자', '유상증자')
            args = mock_ev.call_args[0]
            assert args[1] == '00126380'
