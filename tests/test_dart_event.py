# -*- coding: utf-8 -*-
# test_dart_event.py — dart_event 모듈 단위 테스트

import os
import sys
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opendart_mcp import dart_event
from tests.conftest import (
    FAKE_API_KEY,
    SAMPLE_EVENT_RECORDS,
    make_event_response,
    make_event_empty_response,
)


# ── event() 유효 키워드 테스트 ─────────────────────────────────────────────────

class TestEventValidKeyword:
    def test_returns_dataframe_for_valid_keyword(self):
        """유효한 키워드로 호출하면 이벤트 목록 DataFrame을 반환한다."""
        with patch('requests.get', return_value=make_event_response()):
            df = dart_event.event(FAKE_API_KEY, '00126380', '유상증자')
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_returned_dataframe_has_corp_name_column(self):
        """반환된 DataFrame에 corp_name 컬럼이 있다."""
        with patch('requests.get', return_value=make_event_response()):
            df = dart_event.event(FAKE_API_KEY, '00126380', '유상증자')
        assert 'corp_name' in df.columns

    def test_returns_empty_dataframe_when_status_not_000(self):
        """status가 000이 아니면 빈 DataFrame을 반환한다."""
        with patch('requests.get', return_value=make_event_empty_response(status='013')):
            df = dart_event.event(FAKE_API_KEY, '00126380', '유상증자')
        assert df.empty

    def test_returns_empty_dataframe_when_no_list_key(self):
        """응답에 list 키가 없으면 빈 DataFrame을 반환한다."""
        with patch('requests.get', return_value=make_event_empty_response(status='000')):
            df = dart_event.event(FAKE_API_KEY, '00126380', '유상증자')
        assert df.empty

    def test_requests_correct_endpoint_for_keyword(self):
        """키워드에 매핑된 올바른 DART 엔드포인트로 요청한다."""
        with patch('requests.get', return_value=make_event_response()) as mock_get:
            dart_event.event(FAKE_API_KEY, '00126380', '유상증자')
        call_url = mock_get.call_args[0][0]
        # 유상증자 → piicDecsn
        assert 'piicDecsn.json' in call_url

    def test_requests_correct_endpoint_for_merger_keyword(self):
        """회사합병 키워드는 cmpMgDecsn.json 엔드포인트로 요청한다."""
        with patch('requests.get', return_value=make_event_response()) as mock_get:
            dart_event.event(FAKE_API_KEY, '00126380', '회사합병')
        call_url = mock_get.call_args[0][0]
        assert 'cmpMgDecsn.json' in call_url

    def test_corp_code_in_request_params(self):
        """corp_code가 요청 파라미터에 포함된다."""
        with patch('requests.get', return_value=make_event_response()) as mock_get:
            dart_event.event(FAKE_API_KEY, '00126380', '무상증자')
        call_params = mock_get.call_args[1]['params']
        assert call_params['corp_code'] == '00126380'

    def test_api_key_in_request_params(self):
        """API 키가 crtfc_key로 요청 파라미터에 포함된다."""
        with patch('requests.get', return_value=make_event_response()) as mock_get:
            dart_event.event(FAKE_API_KEY, '00126380', '무상증자')
        call_params = mock_get.call_args[1]['params']
        assert call_params['crtfc_key'] == FAKE_API_KEY

    def test_start_date_defaults_to_far_past(self):
        """start가 None이면 1900-01-01로 설정된다."""
        with patch('requests.get', return_value=make_event_response()) as mock_get:
            dart_event.event(FAKE_API_KEY, '00126380', '유상증자', start=None)
        call_params = mock_get.call_args[1]['params']
        assert call_params['bgn_de'] == '19000101'

    def test_custom_start_date_is_passed_correctly(self):
        """start 날짜가 제공되면 YYYYMMDD 형식으로 파라미터에 포함된다."""
        with patch('requests.get', return_value=make_event_response()) as mock_get:
            dart_event.event(FAKE_API_KEY, '00126380', '유상증자', start='2024-01-01')
        call_params = mock_get.call_args[1]['params']
        assert call_params['bgn_de'] == '20240101'

    def test_all_valid_keywords_do_not_raise(self):
        """key_word_map에 정의된 모든 키워드에 대해 ValueError가 발생하지 않는다."""
        valid_keywords = [
            '부도발생', '영업정지', '회생절차', '해산사유', '유상증자', '무상증자',
            '유무상증자', '감자', '관리절차개시', '소송', '해외상장결정',
        ]
        for kw in valid_keywords:
            with patch('requests.get', return_value=make_event_empty_response(status='000')):
                # ValueError 없이 통과해야 한다
                dart_event.event(FAKE_API_KEY, '00126380', kw)


# ── event() 무효 키워드 테스트 ─────────────────────────────────────────────────

class TestEventInvalidKeyword:
    def test_raises_value_error_for_invalid_keyword(self):
        """key_word_map에 없는 키워드는 ValueError를 발생시킨다."""
        with pytest.raises(ValueError):
            dart_event.event(FAKE_API_KEY, '00126380', '잘못된키워드')

    def test_raises_value_error_for_empty_keyword(self):
        """빈 문자열 키워드는 ValueError를 발생시킨다."""
        with pytest.raises(ValueError):
            dart_event.event(FAKE_API_KEY, '00126380', '')

    def test_raises_value_error_for_english_keyword(self):
        """영어 키워드는 ValueError를 발생시킨다 (map에 없으므로)."""
        with pytest.raises(ValueError):
            dart_event.event(FAKE_API_KEY, '00126380', 'rights_offering')

    def test_does_not_make_http_request_for_invalid_keyword(self):
        """무효 키워드일 때는 HTTP 요청을 하지 않는다."""
        with patch('requests.get') as mock_get:
            with pytest.raises(ValueError):
                dart_event.event(FAKE_API_KEY, '00126380', '잘못된키워드')
        mock_get.assert_not_called()
