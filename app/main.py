# -*- coding: utf-8 -*-
# OpenDartReader — FastAPI REST + FastMCP 통합 서버
import os
import sys
import json
from typing import Optional

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
import pandas as pd
from mcp.server.fastmcp import FastMCP

# __init__.py: sys.modules['OpenDartReader'] = the class itself
import OpenDartReader as _OpenDartReader

DART_API_KEY = os.environ.get('DART_API_KEY', '')


def _get_dart() -> _OpenDartReader:
    if not DART_API_KEY:
        raise RuntimeError("DART_API_KEY 환경변수가 설정되지 않았습니다")
    return _OpenDartReader(DART_API_KEY)


def _df_to_records(df: pd.DataFrame) -> list:
    if df is None or df.empty:
        return []
    return df.where(pd.notnull(df), None).to_dict(orient='records')


def _df_to_json_str(df: pd.DataFrame) -> str:
    return json.dumps(_df_to_records(df), ensure_ascii=False, indent=2)


# ── FastMCP 서버 ──────────────────────────────────────────────────────────────

mcp_server = FastMCP("opendartreader", stateless_http=True)


@mcp_server.tool()
def list_disclosures(
    corp: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    kind: str = '',
    final: bool = True,
) -> str:
    """DART 공시 목록을 조회합니다.
    - corp: 기업명 / 종목코드 / 고유번호 (생략 시 전체)
    - start: 조회 시작일 (예: 2024-01-01)
    - end: 조회 종료일
    - kind: A=정기, B=주요사항, C=발행, D=지분, E=기타, F=외감, G=펀드, H=자산유동화, I=거래소, J=공정위
    - final: 최종보고서만 조회 여부
    """
    dart = _get_dart()
    df = dart.list(corp=corp, start=start, end=end, kind=kind, final=final)
    return _df_to_json_str(df)


@mcp_server.tool()
def get_company(corp: str) -> str:
    """기업 개황 정보를 조회합니다. corp에 종목코드, 기업명, 고유번호 모두 사용 가능합니다."""
    dart = _get_dart()
    result = dart.company(corp)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp_server.tool()
def search_company(name: str) -> str:
    """기업명으로 기업 목록을 검색합니다. 부분 일치를 지원합니다."""
    dart = _get_dart()
    result = dart.company_by_name(name)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp_server.tool()
def find_corp_code(corp: str) -> str:
    """종목코드 또는 기업명으로 DART 고유번호를 조회합니다."""
    dart = _get_dart()
    code = dart.find_corp_code(corp)
    if not code:
        return json.dumps({"error": f"기업을 찾을 수 없습니다: {corp}"}, ensure_ascii=False)
    return json.dumps({"corp": corp, "corp_code": code}, ensure_ascii=False)


@mcp_server.tool()
def get_finstate(corp: str, year: int, reprt_code: str = '11011') -> str:
    """상장기업 재무정보를 조회합니다.
    - corp: 기업명 / 종목코드
    - year: 사업연도 (예: 2023)
    - reprt_code: 11013=1분기, 11012=반기, 11014=3분기, 11011=사업보고서(기본)
    """
    dart = _get_dart()
    df = dart.finstate(corp, year, reprt_code)
    return _df_to_json_str(df)


@mcp_server.tool()
def get_finstate_all(corp: str, year: int, reprt_code: str = '11011', fs_div: str = 'CFS') -> str:
    """단일 회사 전체 재무제표를 조회합니다.
    - fs_div: CFS=연결재무제표(기본), OFS=별도재무제표
    """
    dart = _get_dart()
    df = dart.finstate_all(corp, year, reprt_code, fs_div)
    return _df_to_json_str(df)


@mcp_server.tool()
def get_report(corp: str, key_word: str, year: int, reprt_code: str = '11011') -> str:
    """사업보고서 항목을 조회합니다.
    key_word 가능 값: 증자, 배당, 자기주식, 최대주주, 최대주주변동, 소액주주, 임원, 직원,
    임원개인보수, 임원전체보수, 개인별보수, 타법인출자, 회계감사, 사외이사 등
    """
    dart = _get_dart()
    df = dart.report(corp, key_word, year, reprt_code)
    return _df_to_json_str(df)


@mcp_server.tool()
def get_major_shareholders(corp: str) -> str:
    """대량보유 상황보고(5% 이상 주주)를 조회합니다."""
    dart = _get_dart()
    df = dart.major_shareholders(corp)
    return _df_to_json_str(df)


@mcp_server.tool()
def get_major_shareholders_exec(corp: str) -> str:
    """임원·주요주주 소유보고를 조회합니다."""
    dart = _get_dart()
    df = dart.major_shareholders_exec(corp)
    return _df_to_json_str(df)


@mcp_server.tool()
def get_event(corp: str, key_word: str, start: Optional[str] = None, end: Optional[str] = None) -> str:
    """주요사항보고서를 조회합니다.
    key_word 예: 유상증자, 무상증자, 감자, 합병, 분할, 전환사채발행, 자기주식취득 등
    """
    dart = _get_dart()
    df = dart.event(corp, key_word, start, end)
    return _df_to_json_str(df)


@mcp_server.tool()
def get_regstate(corp: str, key_word: str, start: Optional[str] = None, end: Optional[str] = None) -> str:
    """증권신고서를 조회합니다.
    key_word 예: 지분증권, 채무증권, 합병, 분할, 주식의포괄적교환이전 등
    """
    dart = _get_dart()
    df = dart.regstate(corp, key_word, start, end)
    return _df_to_json_str(df)


# ── FastAPI REST 서버 ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_server.session_manager.run():
        yield

app = FastAPI(
    title="OpenDartReader API",
    description="금융감독원 전자공시(DART) REST API + MCP 서비스",
    version="0.2.2",
    lifespan=lifespan,
)


def _get_dart_http() -> _OpenDartReader:
    if not DART_API_KEY:
        raise HTTPException(status_code=500, detail="DART_API_KEY 환경변수가 설정되지 않았습니다")
    return _OpenDartReader(DART_API_KEY)


@app.get("/health", summary="헬스체크")
def health():
    return {"status": "ok", "dart_api_key_set": bool(DART_API_KEY)}


@app.get("/list", summary="공시 목록 조회")
def list_disclosures_http(
    corp: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    kind: str = '',
    final: bool = True,
):
    dart = _get_dart_http()
    try:
        df = dart.list(corp=corp, start=start, end=end, kind=kind, final=final)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _df_to_records(df)


@app.get("/company/{corp}", summary="기업 개황 조회")
def company_http(corp: str):
    return _get_dart_http().company(corp)


@app.get("/company/search/{name}", summary="기업명 검색")
def company_by_name_http(name: str):
    return _get_dart_http().company_by_name(name)


@app.get("/corp_code/{corp}", summary="고유번호 조회")
def find_corp_code_http(corp: str):
    dart = _get_dart_http()
    code = dart.find_corp_code(corp)
    if not code:
        raise HTTPException(status_code=404, detail=f"기업을 찾을 수 없습니다: {corp}")
    return {"corp": corp, "corp_code": code}


@app.get("/report/{corp}", summary="사업보고서 항목 조회")
def report_http(corp: str, key_word: str, year: int, reprt_code: str = '11011'):
    dart = _get_dart_http()
    try:
        df = dart.report(corp, key_word, year, reprt_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _df_to_records(df)


@app.get("/finstate/{corp}", summary="재무정보 조회")
def finstate_http(corp: str, year: int, reprt_code: str = '11011'):
    df = _get_dart_http().finstate(corp, year, reprt_code)
    return _df_to_records(df)


@app.get("/finstate/all/{corp}", summary="전체 재무제표 조회")
def finstate_all_http(corp: str, year: int, reprt_code: str = '11011', fs_div: str = 'CFS'):
    dart = _get_dart_http()
    try:
        df = dart.finstate_all(corp, year, reprt_code, fs_div)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _df_to_records(df)


@app.get("/shareholders/{corp}", summary="대량보유 주주 조회")
def major_shareholders_http(corp: str):
    dart = _get_dart_http()
    try:
        df = dart.major_shareholders(corp)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _df_to_records(df)


@app.get("/shareholders/exec/{corp}", summary="임원·주요주주 조회")
def major_shareholders_exec_http(corp: str):
    dart = _get_dart_http()
    try:
        df = dart.major_shareholders_exec(corp)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _df_to_records(df)


@app.get("/event/{corp}", summary="주요사항보고서 조회")
def event_http(corp: str, key_word: str, start: Optional[str] = None, end: Optional[str] = None):
    dart = _get_dart_http()
    try:
        df = dart.event(corp, key_word, start, end)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _df_to_records(df)


@app.get("/regstate/{corp}", summary="증권신고서 조회")
def regstate_http(corp: str, key_word: str, start: Optional[str] = None, end: Optional[str] = None):
    dart = _get_dart_http()
    try:
        df = dart.regstate(corp, key_word, start, end)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _df_to_records(df)


# ── MCP 마운트 ─────────────────────────────────────────────────────────────────
# streamable_http_app() 내부에 /mcp 경로가 이미 있으므로 root에 마운트
app.mount("/", mcp_server.streamable_http_app())
