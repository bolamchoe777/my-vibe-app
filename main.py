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
    page_title="전국 시군구 고령화 지도",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 전국 시군구별 고령화 비율 지도")
st.caption("2015~2026 인구 데이터를 기반으로 최신 연도의 시군구별 65세 이상 고령화 비율을 5단계로 보여줍니다.")

# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 및 캐싱 (st.cache_data 사용으로 빠른 로딩)
# -----------------------------------------------------------------------------
@st.cache_data
def load_geojson():
    """전국 시군구 GeoJSON 경계 데이터를 불러옵니다."""
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(url)
    return response.json()

@st.cache_data
def load_population_data():
    """인구 데이터를 불러와 최신 연도 기준 시군구별 고령화 비율을 계산합니다."""
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # '코드' 열은 10자리 행정동 코드이므로 앞자리 0이 사라지지 않도록 문자열(str) 형태로 불러옵니다.
    df = pd.read_csv(url, compression='gzip', dtype={'코드': str})
    
    # 1. 데이터 내 가장 최신 연도만 선택
    latest_year = df['연도'].max()
    df_latest = df[df['연도'] == latest_year].copy()
    
    # 2. 행정동 코드(10자리) 앞 5자리를 잘라 시군구 코드로 사용
    df_latest['시군구코드'] = df_latest['코드'].str[:5]
    
    # 3. 전체 인구('계_') 및 65세 이상 인구 열 선별
    # '계_'로 시작하는 모든 나이별 열 추출
    total_age_cols = [c for c in df_latest.columns if c.startswith('계_')]
    
    # 65세 이상에 해당하는 '계_' 열만 선별
    def is_elderly_col(col_name):
        # '계_65세' -> '65' 또는 '계_100세 이상' -> '100'
        age_str = col_name.replace('계_', '').replace('세', '').replace(' 이상', '').strip()
        if age_str.isdigit() and int(age_str) >= 65:
            return True
        return False

    elderly_age_cols = [c for c in total_age_cols if is_elderly_col(c)]
    
    # 4. 시군구 단위로 그룹화하여 인구수 합산
    # 시도명, 시군구명은 각 시군구코드의 첫 번째 값(first)으로 대표 설정
    sigungu_summary = df_latest.groupby('시군구코드').agg(
        시도=('시도', 'first'),
        시군구=('시군구', 'first')
    ).reset_index()
    
    # 총인구 및 65세 이상 인구 합산 계산
    sigungu_summary['총인구'] = df_latest.groupby('시군구코드')[total_age_cols].sum().sum(axis=1).values
    sigungu_summary['65세이상인구'] = df_latest.groupby('시군구코드')[elderly_age_cols].sum().sum(axis=1).values
    
    # 5. 고령화 비율(%) 계산
    sigungu_summary['고령화율'] = (sigungu_summary['65세이상인구'] / sigungu_summary['총인구'] * 100).round(2)
    
    # 6. 구간 나누기 (19%, 23%, 28%, 38% 경계값 기준 5단계)
    bins = [-np.inf, 19, 23, 28, 38, np.inf]
    labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']
    
    sigungu_summary['구간'] = pd.cut(
        sigungu_summary['고령화율'], 
        bins=bins, 
        labels=labels, 
        right=False
    )
    
    return latest_year, sigungu_summary

# 데이터 로드
geojson_data = load_geojson()
latest_year, df_map = load_population_data()

st.write(f"📌 **데이터 기준 연도:** {latest_year}년")

# -----------------------------------------------------------------------------
# 3. Plotly 지도 시각화 (단계구분도)
# -----------------------------------------------------------------------------
# 5단계 색상 팔레트 (옅은 파란색 -> 진한 파란색)
color_map = {
    '19% 미만': '#eff3ff',
    '19% 이상 ~ 23% 미만': '#bdd7e7',
    '23% 이상 ~ 28% 미만': '#6baed6',
    '28% 이상 ~ 38% 미만': '#3182bd',
    '38% 이상': '#08519c'
}

category_order = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

# Choropleth 지도 생성
fig = px.choropleth(
    df_map,
    geojson=geojson_data,
    locations='시군구코드',
    featureidkey='properties.코드',  # GeoJSON의 5자리 '코드' 속성과 매칭
    color='구간',
    color_discrete_map=color_map,
    category_orders={'구간': category_order},
    hover_name='시군구',             # 마우스 올렸을 때 제목으로 표시
    hover_data={
        '시군구코드': False,
        '시도': True,
        '고령화율': ':.2f',
        '총인구': ':,d',
        '65세이상인구': ':,d'
    },
    labels={
        '구간': '고령화 비율 구간',
        '고령화율': '고령화 비율(%)',
        '총인구': '총 인구(명)',
        '65세이상인구': '65세 이상 인구(명)'
    }
)

# 지도 배경 타일 없애고 대한민국 영역에 맞추기
fig.update_geos(fitbounds="locations", visible=False)

fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 0},
    height=620,
    legend_title_text="고령화 비율 구간",
    legend=dict(yanchor="top", y=0.98, xanchor="left", x=0.01)
)

# Streamlit에 지도 표시
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 4. 하단 고령화율 상위/하위 10개 지역 표
# -----------------------------------------------------------------------------
st.markdown("---")

col1, col2 = st.columns(2)

# 고령화율 높은 순 상위 10개
top10 = (
    df_map.sort_values(by='고령화율', ascending=False)
    .head(10)[['시도', '시군구', '고령화율', '총인구', '65세이상인구']]
    .reset_index(drop=True)
)
top10.index = top10.index + 1

# 고령화율 낮은 순 하위 10개
bottom10 = (
    df_map.sort_values(by='고령화율', ascending=True)
    .head(10)[['시도', '시군구', '고령화율', '총인구', '65세이상인구']]
    .reset_index(drop=True)
)
bottom10.index = bottom10.index + 1

with col1:
    st.subheader("🔴 고령화 비율 가장 높은 지역 Top 10")
    st.dataframe(
        top10.style.format({
            '고령화율': '{:.2f}%',
            '총인구': '{:,}명',
            '65세이상인구': '{:,}명'
        }),
        use_container_width=True
    )

with col2:
    st.subheader("🔵 고령화 비율 가장 낮은 지역 Top 10")
    st.dataframe(
        bottom10.style.format({
            '고령화율': '{:.2f}%',
            '총인구': '{:,}명',
            '65세이상인구': '{:,}명'
        }),
        use_container_width=True
    )
