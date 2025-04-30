import streamlit as st
import pandas as pd
from google_play_scraper import reviews_all, Sort, exceptions as google_exceptions
from datetime import date, timedelta
import pytz
import requests
import math
import altair as alt
import io  # BytesIO 사용을 위해 import
import re  # 텍스트 정제를 위해 import

# --- Streamlit 페이지 설정 ---
st.set_page_config(layout="wide", page_title="앱 리뷰 대시보드")
st.title("📱 앱 리뷰 대시보드")
st.caption("Google Play와 App Store 리뷰를 동시에 확인하세요.")

# --- 모바일에서도 두 컬럼을 수평으로 유지하기 위한 CSS ---
st.markdown(
    """
    <style>
    @media (max-width: 600px) {
      .stColumns > div {
        width: 50% !important;
        min-width: 50% !important;
        display: inline-block !important;
        float: left;
      }
    }
    /* 다운로드 버튼 컨테이너의 너비를 제한하여 버튼 크기 조절 및 세로 래핑 방지 */
    .stDownloadButton {
        width: auto !important;
        display: inline-block !important;
        white-space: nowrap;
        max-width: 100%;
    }
    .stColumns > div:last-child {
        flex-grow: 0 !important;
        flex-shrink: 0 !important;
        width: 20% !important;
        display: flex;
        justify-content: flex-end;
        align-items: center;
    }
    .stSubheader {
        display: inline-block;
        margin-right: 10px;
        vertical-align: middle;
    }
    .stColumns > div {
        display: flex;
        flex-direction: column;
    }
     div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stSubheader"]) {
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
     }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 텍스트 정제 함수 ---
def clean_text_for_excel(text):
    if pd.isna(text):
        return text
    text = str(text)
    cleaned_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return cleaned_text

# --- 입력 섹션 ---
st.sidebar.header("앱 정보 입력")
google_app_id = st.sidebar.text_input("Google Play 앱 ID (패키지 이름)", "kr.co.kbliSmart")
apple_app_id = st.sidebar.text_input("App Store 앱 ID (numeric ID)", "511711198")
review_count_limit = st.sidebar.slider(
    "최대 리뷰 개수", 50, 200, 200, 10,
    help="App Store RSS 피드로 가져올 리뷰 최대 개수를 설정하세요 (최대 200건)."
)
use_date_filter = st.sidebar.checkbox(
    "시작일자 필터 사용", value=False,
    help="선택 시 특정 날짜 이후 리뷰만 표시합니다."
)
selected_start_date = None
if use_date_filter:
    selected_start_date = st.sidebar.date_input(
        "리뷰 시작일 선택",
        value=date.today() - timedelta(days=30),
        help="선택한 날짜(포함) 이후의 리뷰만 가져옵니다."
    )

# --- 레이아웃: 두 개 열 ---
col1, col2 = st.columns(2)

# --- Google Play Store 리뷰 ---
with col1:
    st.header("🤖 Google Play 리뷰")
    if not google_app_id:
        st.warning("Google Play 앱 ID를 입력하세요.")
    else:
        try:
            with st.spinner(f"'{google_app_id}' 리뷰 로딩 중... (전체)"):
                google_reviews = reviews_all(
                    google_app_id,
                    lang='ko', country='kr', sort=Sort.NEWEST
                )

            if not google_reviews:
                st.info("리뷰를 찾을 수 없습니다.")
            else:
                df_g = pd.DataFrame(google_reviews)
                df_g['at'] = pd.to_datetime(df_g['at'], errors='coerce')
                df_g = df_g[df_g['at'].notna()]

                if use_date_filter and selected_start_date:
                    df_g = df_g[df_g['at'].dt.date >= selected_start_date]

                if df_g.empty:
                    st.info(f"선택일 ({selected_start_date}) 이후 리뷰가 없습니다.")
                else:
                    df_g_disp = df_g[['userName','score','at','content','replyContent','repliedAt']].copy()
                    df_g_disp.columns = ['작성자','평점','리뷰 작성일','리뷰 내용','개발자 답변','답변 작성일']

                    tz = pytz.timezone('Asia/Seoul')
                    for c in ['리뷰 작성일','답변 작성일']:
                        df_g_disp[c] = pd.to_datetime(df_g_disp[c], errors='coerce')
                        df_g_disp[c] = df_g_disp[c].dt.tz_localize('UTC', ambiguous='NaT', nonexistent='NaT')
                        df_g_disp[c] = df_g_disp[c].dt.tz_convert(tz).dt.strftime('%Y-%m-%d %H:%M:%S').fillna('N/A')

                    for col in ['리뷰 내용', '개발자 답변']:
                         if col in df_g_disp.columns:
                             df_g_disp[col] = df_g_disp[col].apply(clean_text_for_excel)

                    # 인덱스 리셋하여 Streamlit 데이터셋 ID 충돌 해결
                    df_g_disp.reset_index(drop=True, inplace=True)

                    # 평점 분포 (Altair 차트)
                    st.subheader("평점 분포")
                    rating_df_g = (
                        df_g_disp['평점']
                        .value_counts()
                        .sort_index()
                        .reset_index()
                        .rename(columns={'index': '평점', '평점': '개수'})
                    )
                    chart_g = (
                        alt.Chart(rating_df_g)
                           .mark_bar()
                           .encode(
                               x=alt.X('평점:O', axis=alt.Axis(title='평점')),
                               y=alt.Y('개수:Q', axis=alt.Axis(title='개수'))
                           )
                    )
                    st.altair_chart(chart_g, use_container_width=True, key='g_rating_chart')

                    # 총 리뷰 개수 및 다운로드 버튼
                    count_col_g, btn_col_g = st.columns([8, 2])
                    with count_col_g:
                         st.subheader(f"{len(df_g_disp)}개 리뷰(전체)")
                    with btn_col_g:
                        excel_buffer_g = io.BytesIO()
                        df_g_disp.to_excel(excel_buffer_g, index=False, engine='openpyxl')
                        excel_buffer_g.seek(0)
                        st.download_button(
                            label="다운로드",
                            data=excel_buffer_g,
                            file_name="google_reviews.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                    # 데이터프레임 출력 (placeholder + key)
                    df_placeholder_g = st.empty()
                    df_placeholder_g.dataframe(df_g_disp, height=500, use_container_width=True, key='g_df')

        except google_exceptions.NotFoundError:
            st.error(f"Google Play 앱 ID '{google_app_id}'를 찾을 수 없습니다. ID를 확인해주세요.")
        except Exception as e:
            st.error(f"Google 리뷰 로딩 오류: {e}")

# --- App Store 리뷰 ---
with col2:
    st.header("🍎 App Store 리뷰")
    if not apple_app_id:
        st.warning("App Store 앱 ID를 입력하세요.")
    else:
        try:
            with st.spinner(f"App Store ID '{apple_app_id}' 리뷰 로딩 중... (최대 {review_count_limit}건)"):
                all_reviews = []
                per_page = 50
                pages_to_fetch = math.ceil(review_count_limit / per_page)

                for page in range(1, pages_to_fetch + 1):
                    url = f"https://itunes.apple.com/kr/rss/customerreviews/page={page}/id={apple_app_id}/json"
                    resp = requests.get(url)
                    resp.raise_for_status()

                    data = resp.json()
                    entries = data.get('feed', {}).get('entry', [])
                    if not entries or (page == 1 and len(entries) <= 1):
                         if page == 1:
                             st.info("App Store 리뷰를 찾을 수 없습니다.")
                         break

                    current_page_reviews = entries[1:] if page == 1 else entries
                    all_reviews.extend(current_page_reviews)
                    if len(all_reviews) >= review_count_limit or len(current_page_reviews) < per_page:
                        break

                reviews = all_reviews[:review_count_limit]

            if reviews:
                df_a = pd.DataFrame([
                    {
                        '작성자': r.get('author', {}).get('name', {}).get('label', 'N/A'),
                        '평점': int(r.get('im:rating', {}).get('label', 0)),
                        '리뷰 작성일': r.get('updated', {}).get('label', None),
                        '버전': r.get('im:version', {}).get('label', 'N/A'),
                        '제목': r.get('title', {}).get('label', 'N/A'),
                        '리뷰 내용': r.get('content', {}).get('label', 'N/A')
                    }
                    for r in reviews
                ])

                df_a['리뷰 작성일'] = pd.to_datetime(df_a['리뷰 작성일'], errors='coerce')
                if use_date_filter and selected_start_date:
                    df_a = df_a[df_a['리뷰 작성일'].dt.date >= selected_start_date]

                if df_a.empty:
                    st.info(f"선택일 ({selected_start_date}) 이후 App Store 리뷰가 없습니다.")
                else:
                    tz = pytz.timezone('Asia/Seoul')
                    df_a['리뷰 작성일'] = df_a['리뷰 작성일'].apply(
                        lambda x: x.tz_localize('UTC', ambiguous='NaT', nonexistent='NaT') if pd.notna(x) and x.tzinfo is None else x
                    )
                    df_a['리뷰 작성일'] = df_a['리뷰 작성일'].dt.tz_convert(tz).dt.strftime('%Y-%m-%d %H:%M:%S')

                    for col in ['제목', '리뷰 내용']:
                         if col in df_a.columns:
                             df_a[col] = df_a[col].apply(clean_text_for_excel)

                    # 인덱스 리셋
                    df_a.reset_index(drop=True, inplace=True)

                    st.subheader("평점 분포")
                    rating_df_a = df_a['평점'].value_counts().sort_index().reset_index()
                    rating_df_a.columns = ['평점','개수']
                    chart_a = alt.Chart(rating_df_a).mark_bar().encode(
                        x=alt.X('평점:O', axis=alt.Axis(title='평점')),
                        y=alt.Y('개수:Q', axis=alt.Axis(title='개수'))
                    )
                    st.altair_chart(chart_a, use_container_width=True, key='a_rating_chart')

                    count_col_a, btn_col_a = st.columns([8, 2])
                    with count_col_a:
                         st.subheader(f"{len(df_a)}개 리뷰(최신)")
                    with btn_col_a:
                        excel_buffer_a = io.BytesIO()
                        df_a.to_excel(excel_buffer_a, index=False, engine='openpyxl')
                        excel_buffer_a.seek(0)
                        st.download_button(
                            label="다운로드",
                            data=excel_buffer_a,
                            file_name="apple_reviews.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                    df_placeholder_a = st.empty()
                    df_placeholder_a.dataframe(df_a, height=500, use_container_width=True, key='a_df')

        except requests.exceptions.RequestException as e:
             st.error(f"App Store RSS 피드 요청 오류: {e}")
        except Exception as e:
            st.error(f"App Store 리뷰 로딩 오류: {e}")

# --- 하단 출처 ---
st.divider()
st.markdown("데이터 출처: google-play-scraper, iTunes RSS API with pagination")
