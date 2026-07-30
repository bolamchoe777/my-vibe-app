import json
import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="전국 시군구 고령화 지도", page_icon="🗺️", layout="wide"
)

st.title("🗺️ 대한민국 시군구별 고령화 지도")
st.caption(
    "65세 이상 인구 비율을 기준(19%, 23%, 28%, 38%)으로 5단계로 구분한 지도입니다."
)


# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 및 캐싱 (성능 향상)
# -----------------------------------------------------------------------------
@st.cache_data
def load_geojson():
    """시군구 GeoJSON 경계 데이터를 불러옵니다."""
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(url)
    return response.json()


@st.cache_data
def load_and_process_population_data():
    """인구 데이터를 불러와 최신 연도 기준 시군구별 65세 이상 비율을 계산합니다."""
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"

    # '코드' 열은 문자열(str)로 읽어서 앞자리 0 손실 방지 및 5자리 추출 준비
    df = pd.read_csv(url, compression="gzip", dtype={"코드": str})

    # 가장 최신 연도 추출 및 데이터 필터링
    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()

    # 행정동 코드(10자리)의 앞 5자리를 잘라 시군구 코드 생성
    df_latest["시군구코드"] = df_latest["코드"].str[:5]

    # 나이별 인구 열 찾기 ('계_'로 시작하는 열들)
    age_cols = [col for col in df_latest.columns if col.startswith("계_")]

    # 65세 이상 인구 열만 선별 ('계_65세' ~ '계_100세 이상')
    # 열 이름에서 숫자만 추출하거나 직접 범위 지정
    elderly_cols = []
    for col in age_cols:
        # '계_100세 이상' 처리 및 숫자 파싱
        age_str = col.replace("계_", "").replace("세", "").replace(" 이상", "")
        if age_str.isdigit() and int(age_str) >= 65:
            elderly_cols.append(col)
        elif "100" in col:  # 100세 이상
            elderly_cols.append(col)

    # 시군구 단위로 총인구 및 65세 이상 인구 합산
    # 시도, 시군구 이름은 대표값(first) 사용
    grouped = (
        df_latest.groupby("시군구코드")
        .agg(
            시도=("시도", "first"),
            시군구=("시군구", "first"),
            총인구수=(age_cols[0], "sum")
            if len(age_cols) == 1
            else (age_cols, "sum"),
            고령인구수=(elderly_cols, "sum"),
        )
        .reset_index()
    )

    # 총인구수 합산 (여러 열의 합)
    grouped["총인구"] = df_latest.groupby("시군구코드")[age_cols].sum().sum(axis=1).values
    grouped["65세이상인구"] = (
        df_latest.groupby("시군구코드")[elderly_cols].sum().sum(axis=1).values
    )

    # 고령화 비율(%) 계산
    grouped["고령화비율"] = (
        grouped["65세이상인구"] / grouped["총인구"] * 100
    ).round(2)

    # 지정된 5개 구간으로 나눔 (19%, 23%, 28%, 38% 기준)
    bins = [-np.inf, 19, 23, 28, 38, np.inf]
    labels = [
        "19% 미만",
        "19% 이상 ~ 23% 미만",
        "23% 이상 ~ 28% 미만",
        "28% 이상 ~ 38% 미만",
        "38% 이상",
    ]

    grouped["구간"] = pd.cut(
        grouped["고령화비율"], bins=bins, labels=labels, right=False
    )

    return latest_year, grouped


# 데이터 로드
geojson_data = load_geojson()
latest_year, df_sigungu = load_and_process_population_data()

st.subheader(f"📅 데이터 기준 연도: {latest_year}년")

# -----------------------------------------------------------------------------
# 3. Plotly 지도 시각화
# -----------------------------------------------------------------------------
# 5단계 구간 색상 설정 (연한 색 -> 진한 색)
color_discrete_map = {
    "19% 미만": "#edf8e9",
    "19% 이상 ~ 23% 미만": "#bae4b3",
    "23% 이상 ~ 28% 미만": "#74c476",
    "28% 이상 ~ 38% 미만": "#31a354",
    "38% 이상": "#006d2c",
}

category_orders = [
    "19% 미만",
    "19% 이상 ~ 23% 미만",
    "23% 이상 ~ 28% 미만",
    "28% 이상 ~ 38% 미만",
    "38% 이상",
]

# 지도 생성
fig = px.choropleth(
    df_sigungu,
    geojson=geojson_data,
    locations="시군구코드",
    featureidkey="properties.코드",
    color="구간",
    color_discrete_map=color_discrete_map,
    category_orders={"구간": category_orders},
    hover_name="시군구",
    hover_data={
        "시군구코드": False,
        "시도": True,
        "고령화비율": ":.2f",
        "총인구": ":,d",
        "65세이상인구": ":,d",
    },
    labels={"고령화비율": "고령화 비율(%)", "구간": "고령화 비율 구간"},
)

# 배경 타일 제거 및 대한민국 영역 맞춤
fig.update_geos(fitbounds="locations", visible=False)

fig.update_layout(
    margin={"r": 0, "t": 20, "l": 0, "b": 0},
    legend_title_text="고령화 비율 구간",
    height=650,
)

# 지도 출력
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 4. 하단 순위 표 출력 (상위 10개 / 하위 10개)
# -----------------------------------------------------------------------------
st.markdown("---")
col1, col2 = st.columns(2)

# 고령화 비율이 높은 순 (상위 10개)
top10 = (
    df_sigungu.sort_values(by="고령화비율", ascending=False)
    .head(10)[["시도", "시군구", "고령화비율", "총인구", "65세이상인구"]]
    .reset_index(drop=True)
)
top10.index = top10.index + 1

# 고령화 비율이 낮은 순 (하위 10개)
bottom10 = (
    df_sigungu.sort_values(by="고령화비율", ascending=True)
    .head(10)[["시도", "시군구", "고령화비율", "총인구", "65세이상인구"]]
    .reset_index(drop=True)
)
bottom10.index = bottom10.index + 1

with col1:
    st.markdown("### 🔴 고령화 비율이 높은 지역 Top 10")
    st.dataframe(
        top10.style.format(
            {
                "고령화비율": "{:.2f}%",
                "총인구": "{:,}명",
                "65세이상인구": "{:,}명",
            }
        ),
        use_container_width=True,
    )

with col2:
    st.markdown("### 🟢 고령화 비율이 낮은 지역 Top 10")
    st.dataframe(
        bottom10.style.format(
            {
                "고령화비율": "{:.2f}%",
                "총인구": "{:,}명",
                "65세이상인구": "{:,}명",
            }
        ),
        use_container_width=True,
    )
