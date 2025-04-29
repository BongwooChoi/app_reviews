import streamlit as st
import pandas as pd
from google_play_scraper import reviews_all, Sort, exceptions as google_exceptions
from datetime import datetime, date, timedelta
import pytz
import requests

# --- Streamlit 페이지 설정 ---
st.set_page_config(layout="wide", page_title="앱 리뷰 대시보드")
st.title("📱 앱 리뷰 대시보드")
st.caption("Google Play와 App Store 리뷰를 동시에 확인하세요.")

# --- 입력 섹션 ---
st.sidebar.header("앱 정보 입력")
google_app_id = st.sidebar.text_input("Google Play 앱 ID (패키지 이름)", "kr.co.kbliSmart")
apple_app_id = st.sidebar.text_input("App Store 앱 ID (numeric ID)", "")
review_count_limit = st.sidebar.slider("최대 리뷰 개수", 50, 1000, 500, 50)

# 시작일자 필터 사용 체크박스
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

# --- Google Play Store 리뷰 (왼쪽) ---
with col1:
    st.header("🤖 Google Play Store 리뷰")
    if google_app_id:
        try:
            with st.spinner(f"'{google_app_id}' 리뷰 로딩 중..."):
                google_reviews = reviews_all(
                    google_app_id,
                    lang='ko', country='kr', sort=Sort.NEWEST
                )[:review_count_limit]

            if google_reviews:
                df_g = pd.DataFrame(google_reviews)
                df_g['at'] = pd.to_datetime(df_g['at'], errors='coerce')
                df_g = df_g[df_g['at'].notna()]
                if use_date_filter and selected_start_date:
                    start_ts = pd.Timestamp(selected_start_date)
                    df_g = df_g[df_g['at'] >= start_ts]

                if df_g.empty:
                    st.info(f"선택일 ({selected_start_date}) 이후 리뷰가 없습니다.")
                else:
                    df_g_disp = df_g[[ 'userName','score','at','content','replyContent','repliedAt']].copy()
                    df_g_disp.columns = ['작성자','평점','리뷰 작성일','리뷰 내용','개발자 답변','답변 작성일']
                    tz = pytz.timezone('Asia/Seoul')
                    for c in ['리뷰 작성일','답변 작성일']:
                        df_g_disp[c] = pd.to_datetime(df_g_disp[c], errors='coerce')
                        df_g_disp[c] = df_g_disp[c].dt.tz_localize('UTC', ambiguous='NaT', nonexistent='NaT')
                        df_g_disp[c] = df_g_disp[c].dt.tz_convert(tz).dt.strftime('%Y-%m-%d %H:%M:%S').fillna('N/A')

                    # 평점 분포
                    st.subheader("평점 분포")
                    counts = df_g_disp['평점'].value_counts().sort_index()
                    st.bar_chart(counts)
                    st.subheader(f"총 {len(df_g_disp)}개 리뷰")
                    st.dataframe(df_g_disp, height=500, use_container_width=True)
            else:
                st.info("리뷰를 찾을 수 없습니다.")
        except google_exceptions.NotFoundError:
            st.error(f"앱 ID '{google_app_id}'를 찾을 수 없습니다.")
        except Exception as e:
            st.error(f"Google 리뷰 로딩 오류: {e}")
    else:
        st.warning("Google Play 앱 ID를 입력하세요.")

# --- App Store 리뷰 (오른쪽) ---
with col2:
    st.header("🍎 App Store 리뷰")
    if apple_app_id:
        try:
            with st.spinner(f"App Store ID '{apple_app_id}' 리뷰 로딩 중..."):
                url = f"https://itunes.apple.com/kr/rss/customerreviews/id={apple_app_id}/json"
                resp = requests.get(url)
                data = resp.json().get('feed', {}).get('entry', [])
                # 첫번째 엔트리는 앱 정보이므로 리뷰만 추출
                reviews = data[1:review_count_limit+1]

            if reviews:
                # DataFrame 변환
                df_a = pd.DataFrame([
                    {
                        '작성자': r['author']['name']['label'],
                        '평점': int(r['im:rating']['label']),
                        '리뷰 작성일': r['updated']['label'],
                        '버전': r['im:version']['label'],
                        '제목': r['title']['label'],
                        '리뷰 내용': r['content']['label']
                    }
                    for r in reviews
                ])
                df_a['리뷰 작성일'] = pd.to_datetime(df_a['리뷰 작성일'], errors='coerce')
                if use_date_filter and selected_start_date:
                    df_a = df_a[df_a['리뷰 작성일'] >= pd.Timestamp(selected_start_date)]

                if df_a.empty:
                    st.info(f"선택일 ({selected_start_date}) 이후 App Store 리뷰가 없습니다.")
                else:
                    # 시간대 변환
                    tz = pytz.timezone('Asia/Seoul')
                    df_a['리뷰 작성일'] = df_a['리뷰 작성일'].dt.tz_localize('UTC', ambiguous='NaT', nonexistent='NaT')
                    df_a['리뷰 작성일'] = df_a['리뷰 작성일'].dt.tz_convert(tz).dt.strftime('%Y-%m-%d %H:%M:%S')

                    # 평점 분포
                    st.subheader("평점 분포")
                    counts = df_a['평점'].value_counts().sort_index()
                    st.bar_chart(counts)
                    st.subheader(f"총 {len(df_a)}개 리뷰")
                    st.dataframe(df_a, height=500, use_container_width=True)
            else:
                st.info("App Store 리뷰를 찾을 수 없습니다.")
        except Exception as e:
            st.error(f"App Store 리뷰 로딩 오류: {e}")
    else:
        st.warning("App Store 앱 ID를 입력하세요.")

# --- 하단 출처 ---
st.divider()
st.markdown("데이터 출처: `google-play-scraper`, iTunes RSS API")
