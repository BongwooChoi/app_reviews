import streamlit as st
import pandas as pd
from google_play_scraper import reviews_all, Sort, exceptions as google_exceptions
from app_store_scraper import AppStore
from datetime import datetime
import pytz # 시간대 처리를 위해 pytz 추가

# --- Streamlit 페이지 설정 ---
st.set_page_config(layout="wide", page_title="앱 리뷰 대시보드")
st.title("📊 앱 리뷰 대시보드")
st.caption("Google Play Store와 Apple App Store의 앱 리뷰를 확인하세요.")

# --- 입력 섹션 ---
st.sidebar.header("앱 정보 입력")
# Google Play 앱 ID 기본값을 'kr.co.kbliSmart'로 설정
google_app_id = st.sidebar.text_input("Google Play 앱 ID (패키지 이름)", "kr.co.kbliSmart")
# App Store 앱 ID 입력으로 변경하고 기본값을 '511711198'로 설정
app_store_app_id = st.sidebar.text_input("App Store 앱 ID", "511711198")
# --- App Store 앱 이름 입력 필드 추가 및 기본값 설정 ---
app_store_app_name = st.sidebar.text_input("App Store 앱 이름", "kb라이프생명") # 앱 이름 기본값 설정
# --------------------------------------
app_store_country = st.sidebar.selectbox(
    "App Store 국가 코드",
    ['kr', 'us', 'jp', 'gb', 'de', 'fr', 'cn'], # 주요 국가 코드 예시
    index=0 # 기본값 'kr'
)
review_count_limit = st.sidebar.slider("최대 리뷰 개수 (스토어별)", 50, 1000, 200, 50) # 리뷰 개수 제한 슬라이더 추가

# --- 레이아웃 설정 (2개 컬럼) ---
col1, col2 = st.columns(2)

# --- Google Play Store 리뷰 (왼쪽 컬럼) ---
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
                    # count=review_count_limit # reviews_all은 count 매개변수를 지원하지 않음 (모든 리뷰 가져옴)
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

# --- Apple App Store 리뷰 (오른쪽 컬럼) ---
with col2:
    st.header("🍎 Apple App Store")
    # 앱 ID, 국가 코드, 앱 이름이 모두 입력되었는지 확인
    if app_store_app_id and app_store_country and app_store_app_name: # app_name 조건 추가
        # 앱 ID가 숫자로만 구성되었는지 확인 (기본적인 유효성 검사)
        if app_store_app_id.isdigit():
            try:
                # 앱 ID와 이름을 사용하여 로딩 메시지 표시
                with st.spinner(f"App Store 앱 '{app_store_app_name}' (ID: {app_store_app_id}, 국가: {app_store_country}) 리뷰 로딩 중..."):
                    # app_id, country, app_name을 모두 사용하여 AppStore 객체 생성
                    # app-store-scraper 라이브러리는 일반적으로 앱 ID와 앱 이름 모두를 필요로 합니다.
                    app_store = AppStore(country=app_store_country, app_id=app_store_app_id, app_name=app_store_app_name) # app_name 인자 추가
                    # 리뷰 개수 제한 적용
                    app_store.review(how_many=review_count_limit)

                if app_store.reviews:
                    st.success(f"총 {len(app_store.reviews)}개의 리뷰를 가져왔습니다 (최대 {review_count_limit}개).")
                    # DataFrame 생성 및 필요한 컬럼 선택, 날짜 형식 변환
                    df_apple = pd.DataFrame(app_store.reviews)
                    df_apple_display = df_apple[['userName', 'rating', 'date', 'title', 'review']].copy()
                    df_apple_display.rename(columns={
                        'userName': '작성자',
                        'rating': '평점',
                        'date': '리뷰 작성일',
                        'title': '리뷰 제목',
                        'review': '리뷰 내용'
                    }, inplace=True)

                    # 날짜/시간 컬럼을 한국 시간대로 변환하고 형식 지정 (NaT 처리 포함)
                    kst = pytz.timezone('Asia/Seoul')
                    # NaT(Not a Time) 값을 먼저 처리하고 시간대 변환 및 형식 지정
                    df_apple_display['리뷰 작성일'] = pd.to_datetime(df_apple_display['리뷰 작성일'], errors='coerce')
                     # 시간대 정보가 없는 경우 UTC로 가정하고 변환
                    if df_apple_display['리뷰 작성일'].dt.tz is None:
                         df_apple_display['리뷰 작성일'] = df_apple_display['리뷰 작성일'].dt.tz_localize('UTC')
                    df_apple_display['리뷰 작성일'] = df_apple_display['리뷰 작성일'].dt.tz_convert(kst)
                    df_apple_display['리뷰 작성일'] = df_apple_display['리뷰 작성일'].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('N/A')


                    # 평점 분포 시각화 (선택 사항)
                    st.subheader("평점 분포")
                    # 평점 컬럼이 숫자인지 확인 후 처리
                    if pd.api.types.is_numeric_dtype(df_apple_display['평점']):
                        score_counts_apple = df_apple_display['평점'].value_counts().sort_index()
                        st.bar_chart(score_counts_apple)
                    else:
                        st.warning("평점 데이터가 유효하지 않아 분포를 표시할 수 없습니다.")

                    # 리뷰 데이터 표시
                    st.subheader(f"최신 리뷰 (최대 {review_count_limit}개)")
                    st.dataframe(df_apple_display, height=600, use_container_width=True) # 너비 자동 조절

                else:
                    st.info(f"App Store 앱 '{app_store_app_name}' (ID: {app_store_app_id}, 국가: {app_store_country})에 대한 리뷰를 찾을 수 없습니다.")

            except Exception as e:
                # App Store 스크레이퍼는 특정 앱을 못 찾을 때 일반 Exception을 발생시킬 수 있음
                st.error(f"App Store 리뷰 로딩 중 오류 발생: {e}. 앱 ID, 앱 이름, 국가 코드를 확인해주세요.")
                st.exception(e) # 상세 오류 로그 출력
                st.info("팁: App Store Connect 또는 공개 App Store 페이지에서 정확한 앱 ID와 이름을 확인하세요.")
        else:
            st.error("App Store 앱 ID는 숫자로만 입력해주세요.")
    else:
        st.warning("App Store 앱 ID, 앱 이름, 국가 코드를 모두 입력해주세요.") # 경고 메시지 수정

# --- 하단 설명 ---
st.divider()
st.markdown("데이터 출처: `google-play-scraper`, `app-store-scraper` 라이브러리")
