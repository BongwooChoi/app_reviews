import streamlit as st
import pandas as pd
from google_play_scraper import reviews_all, Sort, exceptions as google_exceptions
from datetime import datetime, date, timedelta
import pytz

# --- Streamlit 페이지 설정 ---
st.set_page_config(layout="wide", page_title="Google Play 리뷰 대시보드")
st.title("📊 Google Play Store 리뷰 대시보드")
st.caption("Google Play Store 앱 리뷰를 확인하세요.")

# --- 입력 섹션 ---
st.sidebar.header("앱 정보 입력")
google_app_id = st.sidebar.text_input("Google Play 앱 ID (패키지 이름)", "kr.co.kbliSmart")
review_count_limit = st.sidebar.slider("최대 리뷰 개수", 50, 1000, 1000, 50) # 리뷰 개수 제한 슬라이더

# 시작일자 필터 사용 체크박스 (기본값: 해제)
use_date_filter = st.sidebar.checkbox("시작일자 필터 사용", value=False, help="선택 시 특정 날짜 이후 리뷰만 표시합니다.")

# 시작일자 선택 위젯 (체크박스 선택 시에만 표시)
selected_start_date = None # 기본적으로 날짜 선택 안 함
if use_date_filter:
    # 체크박스가 선택된 경우에만 날짜 입력 위젯을 표시
    # 위젯의 기본값은 오늘 날짜로부터 30일 전 등으로 설정할 수 있습니다.
    selected_start_date = st.sidebar.date_input(
        "리뷰 시작일 선택",
        value=date.today() - timedelta(days=30), # 필터 사용 시 기본 날짜 (예: 최근 30일)
        help="선택한 날짜 (포함) 이후의 리뷰만 가져옵니다."
    )

# --- 레이아웃 설정 ---
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
                )
                # 가져온 리뷰 개수를 슬라이더 설정값으로 제한 (필터링 전에 적용)
                google_reviews_limited = google_reviews[:review_count_limit]


            if google_reviews_limited:
                st.success(f"총 {len(google_reviews_limited)}개의 리뷰를 가져왔습니다 (최대 {review_count_limit}개).")

                df_google = pd.DataFrame(google_reviews_limited)

                # 'at' 컬럼이 datetime 타입인지 확인하고, 필요시 변환 (필터링을 위해 필요)
                df_google['at'] = pd.to_datetime(df_google['at'], errors='coerce')

                # --- 선택된 시작일 기준으로 데이터 필터링 (체크박스 선택 시에만 적용) ---
                df_google_filtered = df_google.copy() # 필터링 전 데이터를 복사본으로 초기화

                if use_date_filter and selected_start_date:
                    # 체크박스가 선택되었고 날짜가 유효하게 선택된 경우에만 필터 적용
                    start_timestamp = pd.Timestamp(selected_start_date)
                    df_google_filtered = df_google_filtered[df_google_filtered['at'] >= start_timestamp].copy()

                # --- 필터링 후 데이터가 비어있는지 확인 ---
                if len(df_google_filtered) == 0:
                    if len(df_google_limited) > 0: # 원본 (개수 제한된) 리뷰는 있었지만 필터링 후 없어진 경우
                        if use_date_filter and selected_start_date:
                             st.info(f"선택한 시작일 ({selected_start_date}) 이후의 리뷰를 찾을 수 없습니다. 다른 날짜를 선택해보세요.")
                        # else: 날짜 필터 미사용 시 데이터 0개인 경우는 발생하지 않음 (위에서 google_reviews_limited 체크했으므로)
                    # else: 원본 리뷰 자체가 없었던 경우는 이 블록에 들어오지 않음

                else: # 필터링 후 데이터가 있는 경우
                    # --- 필터링된 데이터로 표시할 DataFrame 준비 ---
                    df_google_display = df_google_filtered[['userName', 'score', 'at', 'content', 'replyContent', 'repliedAt']].copy()

                    # 컬럼 이름 변경
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
                         df_google_display[col] = pd.to_datetime(df_google_display[col], errors='coerce')

                         # 시간대 정보가 없는 경우 UTC로 가정하고 변환
                         if df_google_display[col].dt.tz is None:
                              df_google_display[col] = df_google_display[col].dt.tz_localize('UTC')

                         # KST로 변환하고 문자열로 형식 지정
                         df_google_display[col] = df_google_display[col].dt.tz_convert(kst).dt.strftime('%Y-%m-%d %H:%M:%S').fillna('N/A')


                    # --- 필터링된 데이터 기반으로 시각화 및 표시 ---

                    # 평점 분포 시각화
                    st.subheader("평점 분포")
                    if pd.api.types.is_numeric_dtype(df_google_display['평점']):
                        score_counts = df_google_display['평점'].value_counts().sort_index()
                        st.bar_chart(score_counts)
                    else:
                        st.warning("필터링된 평점 데이터가 유효하지 않아 분포를 표시할 수 없습니다.")

                    # 리뷰 데이터 표시 제목 동적 변경
                    review_count_text = f"총 {len(df_google_filtered)}개 리뷰"
                    if use_date_filter and selected_start_date:
                         subheader_text = f"선택일 ({selected_start_date}) 이후 최신 리뷰 ({review_count_text})"
                    else:
                         subheader_text = f"최신 리뷰 (최대 {review_count_limit}개, {review_count_text})"

                    st.subheader(subheader_text)
                    st.dataframe(df_google_display, height=600, use_container_width=True)

            else: # google_reviews_limited가 비어있을 경우 (초기 리뷰 로딩 실패)
                 st.info("해당 앱 ID에 대한 리뷰를 찾을 수 없습니다.")


        except google_exceptions.NotFoundError:
            st.error(f"Google Play Store에서 앱 ID '{google_app_id}'를 찾을 수 없습니다. 앱 ID를 확인해주세요.")
        except Exception as e:
            st.error(f"Google Play Store 리뷰 로딩 및 처리 중 오류 발생: {type(e).__name__}: {e}")
            st.exception(e)
    else:
        st.warning("Google Play 앱 ID를 입력해주세요.")


# --- 하단 설명 ---
st.divider()
st.markdown("데이터 출처: `google-play-scraper` 라이브러리")
