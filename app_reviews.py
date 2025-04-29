import streamlit as st
import pandas as pd
from google_play_scraper import reviews_all, Sort, exceptions as google_exceptions
from datetime import datetime, date, timedelta # date와 timedelta 추가
import pytz # 시간대 처리를 위해 pytz 추가

# --- Streamlit 페이지 설정 ---
st.set_page_config(layout="wide", page_title="Google Play 리뷰 대시보드")
st.title("📊 Google Play Store 리뷰 대시보드")
st.caption("Google Play Store 앱 리뷰를 확인하세요.")

# --- 입력 섹션 ---
st.sidebar.header("앱 정보 입력")
# Google Play 앱 ID 기본값을 'kr.co.kbliSmart'로 설정
google_app_id = st.sidebar.text_input("Google Play 앱 ID (패키지 이름)", "kr.co.kbliSmart")
# 리뷰 개수 제한 슬라이더의 기본값을 1000으로 변경
review_count_limit = st.sidebar.slider("최대 리뷰 개수", 50, 1000, 1000, 50) # 리뷰 개수 제한 슬라이더

# 리뷰 시작일 선택 위젯 추가 (기본값: 오늘로부터 90일 전)
default_start_date = date.today() - timedelta(days=90)
selected_start_date = st.sidebar.date_input(
    "리뷰 시작일 선택",
    value=default_start_date,
    help="선택한 날짜 (포함) 이후의 리뷰만 표시합니다."
)

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
                    lang='ko',          # 언어: 한국어
                    country='kr',       # 국가: 대한민국
                    sort=Sort.NEWEST,   # 정렬: 최신순
                    # reviews_all은 count 매개변수를 지원하지 않으므로, 슬라이싱으로 개수 제한
                )
                # 가져온 리뷰 개수를 슬라이더 설정값으로 제한
                google_reviews_limited = google_reviews[:review_count_limit]


            if google_reviews_limited:
                st.success(f"총 {len(google_reviews_limited)}개의 리뷰를 가져왔습니다 (최대 {review_count_limit}개).")

                # DataFrame 생성
                df_google = pd.DataFrame(google_reviews_limited)

                # 'at' 컬럼이 datetime 타입인지 확인하고, 필요시 변환 (필터링을 위해 필요)
                df_google['at'] = pd.to_datetime(df_google['at'], errors='coerce')

                # --- 선택된 시작일 기준으로 데이터 필터링 ---
                # 선택된 날짜의 자정 (00:00:00)부터를 기준으로 필터링
                start_timestamp = pd.Timestamp(selected_start_date)
                df_google_filtered = df_google[df_google['at'] >= start_timestamp].copy() # 필터링 후 복사본 생성

                # 필터링 후 데이터가 비어있는지 확인
                if len(df_google_filtered) == 0:
                    if len(df_google) > 0: # 원본 리뷰는 있었지만 필터링 후 없어진 경우
                         st.info(f"선택한 시작일 ({selected_start_date}) 이후의 리뷰를 찾을 수 없습니다. 다른 날짜를 선택해보세요.")
                    else: # 원본 리뷰 자체가 없었던 경우 (위 success 메시지 이후 처리)
                         st.info("해당 앱 ID에 대한 리뷰를 찾을 수 없습니다.")
                else:
                    # --- 필터링된 데이터로 표시할 DataFrame 준비 ---
                    # 필요한 컬럼 선택
                    df_google_display = df_google_filtered[['userName', 'score', 'at', 'content', 'replyContent', 'repliedAt']].copy()

                    # 컬럼 이름 변경
                    df_google_display.rename(columns={
                        'userName': '작성자',
                        'score': '평점',
                        'at': '리뷰 작성일', # 아직 datetime 객체
                        'content': '리뷰 내용',
                        'replyContent': '개발자 답변',
                        'repliedAt': '답변 작성일' # 아직 datetime 객체
                    }, inplace=True)

                    # 날짜/시간 컬럼을 한국 시간대로 변환하고 형식 지정 (NaT 처리 포함)
                    kst = pytz.timezone('Asia/Seoul')
                    for col in ['리뷰 작성일', '답변 작성일']:
                         # NaT(Not a Time) 값을 먼저 처리하고 시간대 변환 및 형식 지정
                         # 이미 datetime 객체이므로 바로 변환 및 형식 지정
                         df_google_display[col] = pd.to_datetime(df_google_display[col], errors='coerce') # 안전을 위해 다시 확인
                         # 시간대 정보가 없는 경우 UTC로 가정하고 변환
                         if df_google_display[col].dt.tz is None:
                              # Review 'at' timestamps from google-play-scraper are typically UTC,
                              # but let's explicitly handle potential no-tz data robustly.
                              df_google_display[col] = df_google_display[col].dt.tz_localize('UTC', errors='coerce')
                         # Convert to KST and format
                         df_google_display[col] = df_google_display[col].dt.tz_convert(kst).dt.strftime('%Y-%m-%d %H:%M:%S').fillna('N/A')


                    # --- 필터링된 데이터 기반으로 시각화 및 표시 ---

                    # 평점 분포 시각화
                    st.subheader("평점 분포")
                    # 필터링된 평점 컬럼이 숫자인지 확인 후 처리
                    if pd.api.types.is_numeric_dtype(df_google_display['평점']):
                        score_counts = df_google_display['평점'].value_counts().sort_index()
                        st.bar_chart(score_counts)
                    else:
                        st.warning("필터링된 평점 데이터가 유효하지 않아 분포를 표시할 수 없습니다.")


                    # 리뷰 데이터 표시
                    st.subheader(f"선택일 ({selected_start_date}) 이후 리뷰 ({len(df_google_filtered)}개)") # 필터링된 개수 표시
                    st.dataframe(df_google_display, height=600, use_container_width=True)

            # else: # 이 부분은 google_reviews_limited가 비어있을 때 처리하므로 위쪽으로 이동

        except google_exceptions.NotFoundError:
            st.error(f"Google Play Store에서 앱 ID '{google_app_id}'를 찾을 수 없습니다. 앱 ID를 확인해주세요.")
        except Exception as e:
            st.error(f"Google Play Store 리뷰 로딩 및 처리 중 오류 발생: {e}")
            st.exception(e) # 상세 오류 로그 출력
    else:
        st.warning("Google Play 앱 ID를 입력해주세요.")


# --- 하단 설명 ---
st.divider()
st.markdown("데이터 출처: `google-play-scraper` 라이브러리")
