import streamlit as st
import pandas as pd
from google_play_scraper import reviews_all, Sort, exceptions as google_exceptions
from datetime import date, timedelta
import pytz
import requests
import math
import altair as alt

# --- Streamlit 페이지 설정 ---
st.set_page_config(layout="wide", page_title="앱 리뷰 대시보드")
st.title("📱 앱 리뷰 대시보드")
st.caption("Google Play와 App Store 리뷰를 동시에 확인하세요.")

# --- 모바일 및 버튼 스타일 ---
st.markdown(
    """
    <style>
    /* 모바일 화면에서 두 컬럼 50%씩 */
    @media (max-width: 600px) {
      .stColumns > div {
        width: 50% !important;
        display: inline-block !important;
      }
    }
    /* 다운로드 버튼 컴팩트하게 */
    .stDownloadButton button {
      padding: 0.25em 0.5em !important;
      font-size: 0.9em !important;
      line-height: 1.2em !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 입력 섹션 ---
st.sidebar.header("앱 정보 입력")
google_app_id = st.sidebar.text_input("Google Play 앱 ID", "kr.co.kbliSmart")
apple_app_id = st.sidebar.text_input("App Store 앱 ID", "511711198")
review_count_limit = st.sidebar.slider(
    "최대 리뷰 개수", 50, 200, 200, 10,
    help="App Store RSS 피드로 가져올 리뷰 최대 개수를 설정"
)
use_date_filter = st.sidebar.checkbox("시작일자 필터 사용", value=False)
selected_start_date = None
if use_date_filter:
    selected_start_date = st.sidebar.date_input(
        "리뷰 시작일 선택", value=date.today() - timedelta(days=30)
    )

# --- 레이아웃 ---
col1, col2 = st.columns(2)

# --- Google Play 리뷰 ---
with col1:
    st.header("🤖 Google Play 리뷰")
    if not google_app_id:
        st.warning("Google Play 앱 ID를 입력하세요.")
    else:
        try:
            google_reviews = reviews_all(
                google_app_id, lang='ko', country='kr', sort=Sort.NEWEST
            )
            df_g = pd.DataFrame(google_reviews)
            df_g['at'] = pd.to_datetime(df_g['at'], errors='coerce')
            if use_date_filter and selected_start_date:
                df_g = df_g[df_g['at'].dt.date >= selected_start_date]
            df_g = df_g.dropna(subset=['at'])

            if df_g.empty:
                st.info("해당 조건에 맞는 리뷰가 없습니다.")
            else:
                df_g_disp = df_g[['userName','score','at','content','replyContent','repliedAt']].copy()
                df_g_disp.columns = ['작성자','평점','리뷰 작성일','리뷰 내용','개발자 답변','답변 작성일']
                tz = pytz.timezone('Asia/Seoul')
                for c in ['리뷰 작성일','답변 작성일']:
                    df_g_disp[c] = pd.to_datetime(df_g_disp[c], errors='coerce')
                    df_g_disp[c] = df_g_disp[c].dt.tz_localize('UTC', nonexistent='NaT')
                    df_g_disp[c] = df_g_disp[c].dt.tz_convert(tz).dt.strftime('%Y-%m-%d %H:%M:%S')

                st.subheader("평점 분포")
                st.bar_chart(df_g_disp['평점'].value_counts().sort_index())
                st.subheader(f"총 {len(df_g_disp)}개 리뷰")

                csv_g = df_g_disp.to_csv(index=False).encode('utf-8')
                _, btn = st.columns([8,1])
                with btn:
                    st.download_button(
                        "다운로드",
                        data=csv_g,
                        file_name="google_reviews.csv",
                        mime="text/csv"
                    )

                st.dataframe(df_g_disp, height=500, use_container_width=True)
        except google_exceptions.NotFoundError:
            st.error("Google Play 앱을 찾을 수 없습니다.")
        except Exception as e:
            st.error(f"Google 리뷰 로딩 오류: {e}")

# --- App Store 리뷰 ---
with col2:
    st.header("🍎 App Store 리뷰")
    if not apple_app_id:
        st.warning("App Store 앱 ID를 입력하세요.")
    else:
        try:
            all_reviews = []
            per_page = 50
            pages = math.ceil(review_count_limit / per_page)
            for page in range(1, pages+1):
                url = f"https://itunes.apple.com/kr/rss/customerreviews/page={page}/id={apple_app_id}/json"
                data = requests.get(url).json().get('feed', {}).get('entry', [])
                if len(data) <= 1:
                    break
                entries = data[1:] if page==1 else data
                all_reviews += entries
                if len(entries) < per_page:
                    break
            reviews = all_reviews[:review_count_limit]
            df_a = pd.DataFrame([
                {'작성자':r['author']['name']['label'], '평점':int(r['im:rating']['label']),
                 '리뷰 작성일':r['updated']['label'], '버전':r['im:version']['label'],
                 '제목':r['title']['label'], '리뷰 내용':r['content']['label']}
                for r in reviews
            ])
            df_a['리뷰 작성일'] = pd.to_datetime(df_a['리뷰 작성일'], errors='coerce')
            if use_date_filter and selected_start_date:
                df_a = df_a[df_a['리뷰 작성일'].dt.date >= selected_start_date]
            tz = pytz.timezone('Asia/Seoul')
            # tz-aware 처리: tz info 없으면 UTC로 로컬라이즈
                    def ensure_utc(x):
                        if x.tzinfo is None:
                            return x.tz_localize('UTC')
                        return x
                    df_a['리뷰 작성일'] = df_a['리뷰 작성일'].apply(ensure_utc)
            df_a['리뷰 작성일'] = df_a['리뷰 작성일'].dt.tz_convert(tz).dt.strftime('%Y-%m-%d %H:%M:%S')

            if df_a.empty:
                st.info("App Store 리뷰가 없습니다.")
            else:
                st.subheader("평점 분포")
                counts = df_a['평점'].value_counts().sort_index().reset_index()
                counts.columns = ['평점','count']
                chart = alt.Chart(counts).mark_bar(color='red').encode(
                    x=alt.X('평점:O', axis=alt.Axis(title=None)),
                    y=alt.Y('count:Q', axis=alt.Axis(title=None))
                )
                st.altair_chart(chart, use_container_width=True)
                st.subheader(f"총 {len(df_a)}개 리뷰")

                csv_a = df_a.to_csv(index=False).encode('utf-8')
                _, btn2 = st.columns([8,1])
                with btn2:
                    st.download_button(
                        "다운로드",
                        data=csv_a,
                        file_name="apple_reviews.csv",
                        mime="text/csv"
                    )
                st.dataframe(df_a, height=500, use_container_width=True)
        except Exception as e:
            st.error(f"App Store 리뷰 로딩 오류: {e}")

# --- 하단 출처 ---

st.divider()
st.markdown("데이터 출처: `google-play-scraper`, iTunes RSS API")
