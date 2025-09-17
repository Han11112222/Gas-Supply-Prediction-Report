# app.py — 2026 도시가스 공급량 사업계획(스트림릿·깃허브 자동갱신 템플릿)
from __future__ import annotations
import os, io, time, hashlib, glob
from pathlib import Path
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="2026 도시가스 공급량 사업계획", layout="wide")

# ─────────────────────────────────────────────────────────────
# 유틸: 파일 해시 → 데이터 변경 시 cache 무효화(오토 리프레시)
# ─────────────────────────────────────────────────────────────
def file_md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

@st.cache_data(show_spinner=False)
def load_excel(path: Path) -> dict[str, pd.DataFrame]:
    # 여러 시트 읽기 → dict 반환
    xls = pd.ExcelFile(path)
    return {name: xls.parse(name) for name in xls.sheet_names}

def pick_latest(patterns: list[str]) -> Path | None:
    cands = []
    for pat in patterns:
        cands += glob.glob(pat)
    if not cands:
        return None
    cands = sorted(cands, key=lambda p: Path(p).stat().st_mtime, reverse=True)
    return Path(cands[0])

# ─────────────────────────────────────────────────────────────
# 데이터 소스 선택: 업로드 or 리포 data/ 최신본 자동 감지
# ─────────────────────────────────────────────────────────────
st.sidebar.header("데이터 소스")
uploaded_supply = st.sidebar.file_uploader("공급량(엑셀)", type=["xlsx"])
uploaded_weather = st.sidebar.file_uploader("기온/시나리오(엑셀)", type=["xlsx"])
uploaded_industry = st.sidebar.file_uploader("산업/업종(엑셀)", type=["xlsx"])

repo_supply = pick_latest(["data/supply_*.xlsx", "data/*supply*.xlsx"])
repo_weather = pick_latest(["data/weather_*.xlsx", "data/*weather*.xlsx"])
repo_industry = pick_latest(["data/industry_*.xlsx", "data/*industry*.xlsx"])

# 업로드 우선, 없으면 repo 파일
supply_src = "upload" if uploaded_supply else "repo"
weather_src = "upload" if uploaded_weather else "repo"
industry_src = "upload" if uploaded_industry else "repo"

if uploaded_supply:
    supply_book = pd.ExcelFile(uploaded_supply)
    supply = {s: supply_book.parse(s) for s in supply_book.sheet_names}
elif repo_supply:
    st.sidebar.caption(f"공급량 파일: {repo_supply.name}")
    supply = load_excel(repo_supply)
else:
    supply = {}

if uploaded_weather:
    weather_book = pd.ExcelFile(uploaded_weather)
    weather = {s: weather_book.parse(s) for s in weather_book.sheet_names}
elif repo_weather:
    st.sidebar.caption(f"기온 파일: {repo_weather.name}")
    weather = load_excel(repo_weather)
else:
    weather = {}

if uploaded_industry:
    industry_book = pd.ExcelFile(uploaded_industry)
    industry = {s: industry_book.parse(s) for s in industry_book.sheet_names}
elif repo_industry:
    st.sidebar.caption(f"산업 파일: {repo_industry.name}")
    industry = load_excel(repo_industry)
else:
    industry = {}

# ─────────────────────────────────────────────────────────────
# 수기 입력(요약/문구/파라미터)
# ─────────────────────────────────────────────────────────────
st.sidebar.header("수기 입력(보고서 문구)")
exec_md = st.sidebar.text_area("Executive Summary (Markdown)", value="""
- 2026 총공급량 전망: 기준 ___ TJ (YoY ___%)
- 핵심 드라이버: 기온(±°C), 신규공급 ___세대, 산업가동률 ___, 연료전지 ___MW
- 리스크: 콜드스냅 / 산업 수출 / LNG스팟 변동
""", height=180)

with st.sidebar.expander("핵심 파라미터(예시·편집 가능)"):
    p_cols = ["항목","값"]
    base_params = pd.DataFrame([
        ["세대당 평균사용량(㎥/월)", 30.0],
        ["입주 램프(1~4분기, %)", "30,60,85,100"],
        ["가정용 민감도(㎥/°C·월)", 7800000],
        ["업무용 민감도(㎥/°C·월)", 1200000],
        ["온난 편차(°C)", 0.5],
        ["한랭 편차(°C)", -1.0],
    ], columns=p_cols)
    params = st.data_editor(base_params, num_rows="dynamic", use_container_width=True)

def get_param(name:str, default=None):
    try:
        row = params[params["항목"]==name]["값"].iloc[0]
        return row
    except Exception:
        return default

# ─────────────────────────────────────────────────────────────
# 레이아웃: 공통기준 / 용도별(전체, 가정용, 산업용, 업무용, 열병합)
# ─────────────────────────────────────────────────────────────
st.title("2026 도시가스 공급량 사업계획")
tabs = st.tabs(["공통기준","전체공급량","가정용","산업용","업무용","열병합·연료전지","요약출력"])

# 1) 공통기준
with tabs[0]:
    st.subheader("기온 기준·시나리오")
    if weather:
        # 기대 스키마: weather["scenarios"]에 월, 평년, 기준, 온난, 한랭 열
        ws = list(weather.values())[0].copy()
        st.dataframe(ws, use_container_width=True, hide_index=True)
        # 시나리오 간단 시각화
        if {"월","평년","기준","온난","한랭"}.issubset(set(ws.columns)):
            fig, ax = plt.subplots()
            ax.plot(ws["월"], ws["평년"], label="평년")
            ax.plot(ws["월"], ws["기준"], label="기준")
            ax.plot(ws["월"], ws["온난"], label="온난")
            ax.plot(ws["월"], ws["한랭"], label="한랭")
            ax.set_xlabel("월"); ax.set_ylabel("°C"); ax.legend()
            st.pyplot(fig, use_container_width=True)
        st.caption("※ KMA 평년값·3개월전망과 내부 시나리오를 결합해 월별 편차를 설정.")
    else:
        st.info("기온/시나리오 엑셀을 업로드하거나 data/weather_*.xlsx를 리포에 추가해줘.")

# 2) 전체공급량
with tabs[1]:
    st.subheader("전체공급량(요약)")
    if supply:
        # 기대 스키마: supply["by_use"]에 [연,월,용도,공급량(㎥)]
        df = list(supply.values())[0].copy()
        st.dataframe(df.head(50), use_container_width=True)
        if {"연","월","용도","공급량(㎥)"}.issubset(set(df.columns)):
            g = df.groupby(["연","월","용도"], as_index=False)["공급량(㎥)"].sum()
            g["연월"] = pd.to_datetime(g["연"].astype(str)+"-"+g["월"].astype(str)+"-01")
            pivot = g.pivot_table(index="연월", columns="용도", values="공급량(㎥)", aggfunc="sum").fillna(0)
            st.line_chart(pivot, use_container_width=True)
            st.caption("※ 새 엑셀을 data/ 폴더에 푸시하면 자동으로 갱신됨.")
        else:
            st.warning("열 이름 예시: 연, 월, 용도, 공급량(㎥)")
    else:
        st.info("공급량 엑셀을 업로드하거나 data/supply_*.xlsx를 리포에 추가해줘.")

# 3) 가정용
with tabs[2]:
    st.subheader("가정용 — 기온 시나리오 + 신규공급")
    col1, col2 = st.columns([1,1])
    with col1:
        hh_avg = float(get_param("세대당 평균사용량(㎥/월)", 30))
        ramp = [int(x) for x in str(get_param("입주 램프(1~4분기, %)", "30,60,85,100")).split(",")]
        st.markdown(f"- 세대당 평균사용량: **{hh_avg} ㎥/월**  \n- 입주 램프: **{ramp} %**")
        st.caption("※ 램프는 1~4분기 진행률(예: 30/60/85/100).")
    with col2:
        sens = float(get_param("가정용 민감도(㎥/°C·월)", 7_800_000))
        warm, cold = float(get_param("온난 편차(°C)", 0.5)), float(get_param("한랭 편차(°C)", -1.0))
        st.markdown(f"- 기온 민감도: **{sens:,.0f} ㎥/°C·월**  \n- 온난/한랭: **+{warm}°C / {cold}°C**")
    st.divider()
    st.info("신규 단지 목록(세대수·개시월)을 표에 입력하면 월별 신규물량을 계산합니다.")
    tmpl = pd.DataFrame({"단지":["예: A"],"세대수":[500],"입주개시(YYYY-MM)":["2026-03"]})
    new_sites = st.data_editor(tmpl, num_rows="dynamic", use_container_width=True, key="new_sites")
    # 간단 계산(램프 4분기 적용)
    def monthly_new(hh:int, start:str, avg:float, ramp:list[int]):
        out = []
        y, m = map(int, start.split("-"))
        for i,p in enumerate(ramp):
            ym = pd.Period(f"{y}-{m}", freq="M") + i
            out.append({"연월": ym.to_timestamp(), "신규물량(㎥)": hh*avg*(p/100)})
        return pd.DataFrame(out)
    calc = []
    for _,r in new_sites.dropna().iterrows():
        try:
            calc.append(monthly_new(int(r["세대수"]), str(r["입주개시(YYYY-MM)"]), hh_avg, ramp))
        except Exception:
            pass
    if calc:
        new_df = pd.concat(calc).groupby("연월", as_index=False)["신규물량(㎥)"].sum()
        st.area_chart(new_df.set_index("연월"))
        st.download_button("신규공급 계산 CSV 다운로드", new_df.to_csv(index=False).encode("utf-8"), "new_households.csv", "text/csv")

# 4) 산업용
with tabs[3]:
    st.subheader("산업용 — 가동률/수출 민감도(요약)")
    st.caption("※ 업종별(예: 금속/자동차부품/섬유) 데이터 업로드 시 추세·상관 확인")
    if industry:
        idf = list(industry.values())[0].copy()
        st.dataframe(idf.head(50), use_container_width=True)
    st.info("업종 Top10, PMI/가동률 연동 회귀는 추후 데이터 컬럼명에 맞춰 연결.")

# 5) 업무용·열병합
with tabs[4]:
    st.subheader("업무용 — 서비스지수/HDD·CDD")
    st.info("업무용은 서비스지수 및 냉난방도일(HDD/CDD)와의 민감도 분석 연결 예정.")

with tabs[5]:
    st.subheader("열병합·연료전지 — 설비 스케줄·이용률")
    st.info("설비별 kW·이용률·효율을 표로 입력 후 월별 ㎥ 산출 (다운로드 제공).")

# 6) 요약 출력(수기 작성 + 내보내기)
with tabs[6]:
    st.subheader("Executive Summary (미리보기)")
    st.markdown(exec_md)
    st.download_button("요약(MD) 다운로드", exec_md.encode("utf-8"), "executive_summary.md", "text/markdown")
    st.success("데이터 파일 교체/푸시 → 자동 리빌드/자동 그래프 갱신")
