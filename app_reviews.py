import streamlit as st
import pandas as pd
from google_play_scraper import reviews_all, Sort, exceptions as google_exceptions
from datetime import datetime
import pytz # 시간대 처리를 위해 pytz 추가

# --- Streamlit 페이지 설정 ---
st.set_page_config(layout="wide", page_title="Google Play 리뷰 대시보드")
st.title("📊 Google Play Store 리뷰 대시보드")
st.caption("Google Play Store 앱 리뷰를 확인하세요.")

# --- 입력 섹션 ---
st.sidebar.header("앱 정보 입력")
# Google Play 앱 ID 기본값을 'kr.co.kbliSmart'로 설정
google_app_id = st.sidebar.text_input("Google Play 앱 ID (패키지 이름)", "kr.co.kbliSmart")
review_count_limit = st.sidebar.slider("최대 리뷰 개수", 50, 1000, 1000, 50) # 리뷰 개수 제한 슬라이더

# --- 레이아웃 설정 (단일 컬럼) ---
# App Store 부분이 제거되었으므로 단일 컬럼 레이아웃 사용
col1 = st.container()

# --- Google Play Store 리뷰 ---
with col1:
    st.header("🤖 Google Play Store")
    if google_app_id:
        try:
            with st.spinner(f"'{google_app_id}' 앱 리뷰 로딩 중..."):
                google_reviews = reviews_all(
                    google_app_id,
                    lang='ko',           # 언어: 한국어
                    country='kr',        # 국가: 대한민국
                    sort=Sort.NEWEST,    # 정렬: 최신순
                    # reviews_all은 count 매개변수를 지원하지 않으므로, 슬라이싱으로 개수 제한
                )
                # 가져온 리뷰 개수를 제한하려면 슬라이싱 사용
                google_reviews = google_reviews[:review_count_limit]


            if google_reviews:
                st.success(f"총 {len(google_reviews)}개의 리뷰를 가져왔습니다 (최대 {review_count_limit}개).")
                # DataFrame 생성 및 필요한 컬럼 선택, 날짜 형식 변환
                df_google = pd.DataFrame(google_reviews)
                df_google_display = df_google[['userName', 'score', 'at', 'content', 'replyContent', 'repliedAt']].copy()
                df_google_display.rename(columns={
                    'userName': '작성자',
                    'score': '평점',
                    'at': '리뷰 작성일',
                    'content': '리뷰 내용',
                    'replyContent': '개발자 답변',
                    'repliedAt': '답변 작성일'
                }, inplace=True)

                # 날짜/시간 컬럼을 한국 시간대로 변환하고 형식 지정 (NaT 처리 포함)
                kst = pytz.timezone('Asia/Seoul')
                for col in ['리뷰 작성일', '답변 작성일']:
                     # NaT(Not a Time) 값을 먼저 처리하고 시간대 변환 및 형식 지정
                    df_google_display[col] = pd.to_datetime(df_google_display[col], errors='coerce')
                    # 시간대 정보가 없는 경우 UTC로 가정하고 변환
                    if df_google_display[col].dt.tz is None:
                         df_google_display[col] = df_google_display[col].dt.tz_localize('UTC')
                    df_google_display[col] = df_google_display[col].dt.tz_convert(kst)
                    df_google_display[col] = df_google_display[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('N/A')


                # 평점 분포 시각화 (선택 사항)
                st.subheader("평점 분포")
                # 평점 컬럼이 숫자인지 확인 후 처리
                if pd.api.types.is_numeric_dtype(df_google_display['평점']):
                    score_counts = df_google_display['평점'].value_counts().sort_index()
                    st.bar_chart(score_counts)
                else:
                    st.warning("평점 데이터가 유효하지 않아 분포를 표시할 수 없습니다.")


                # 리뷰 데이터 표시 (DataFrame 또는 Expander)
                st.subheader(f"최신 리뷰 (최대 {review_count_limit}개)")
                st.dataframe(df_google_display, height=600, use_container_width=True) # 너비 자동 조절

            else:
                st.info("해당 앱 ID에 대한 리뷰를 찾을 수 없습니다.")

        except google_exceptions.NotFoundError:
            st.error(f"Google Play Store에서 앱 ID '{google_app_id}'를 찾을 수 없습니다. 앱 ID를 확인해주세요.")
        except Exception as e:
            st.error(f"Google Play Store 리뷰 로딩 중 오류 발생: {e}")
            st.exception(e) # 상세 오류 로그 출력
    else:
        st.warning("Google Play 앱 ID를 입력해주세요.")


# --- 하단 설명 ---
st.divider()
st.markdown("데이터 출처: `google-play-scraper` 라이브러리")
