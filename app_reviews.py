import streamlit as st
import pandas as pd
from google_play_scraper import reviews_all, Sort, exceptions as google_exceptions
from datetime import datetime, date # date 객체 사용을 위해 임포트
import pytz # 시간대 처리를 위해 pytz 추가

# --- Streamlit 페이지 설정 ---
st.set_page_config(layout="wide", page_title="Google Play 리뷰 대시보드")
st.title("📊 Google Play Store 리뷰 대시보드")
st.caption("Google Play Store 앱의 전체 리뷰를 가져와 기간별로 확인하세요.") # 설명 업데이트

# --- 입력 섹션 ---
st.sidebar.header("앱 정보 입력 및 필터")
# Google Play 앱 ID 기본값을 'kr.co.kbliSmart'로 설정
google_app_id = st.sidebar.text_input("Google Play 앱 ID (패키지 이름)", "kr.co.kbliSmart")

# 기간 설정 입력 필드 추가
st.sidebar.subheader("리뷰 기간 설정")
today = date.today()
start_date = st.sidebar.date_input("시작일", value=today - pd.Timedelta(days=365)) # 기본값: 1년 전
end_date = st.sidebar.date_input("종료일", value=today) # 기본값: 오늘

# 최대 표시 리뷰 개수 슬라이더 (기간 필터링 후 적용)
review_count_limit = st.sidebar.slider("최대 표시 리뷰 개수 (기간 필터링 후)", 50, 1000, 200, 50)

# --- 레이아웃 설정 (단일 컬럼) ---
col1 = st.container()

# --- Google Play Store 리뷰 ---
with col1:
    st.header("🤖 Google Play Store")
    if google_app_id:
        try:
            # 모든 리뷰 가져오기 시도
            with st.spinner(f"'{google_app_id}' 앱의 전체 리뷰 로딩 중..."):
                # reviews_all은 내부적으로 페이지네이션을 처리하여 가능한 많은 리뷰를 가져옵니다.
                # count 매개변수는 reviews_all에 없습니다.
                google_reviews = reviews_all(
                    google_app_id,
                    lang='ko',           # 언어: 한국어
                    country='kr',        # 국가: 대한민국
                    sort=Sort.NEWEST,    # 정렬: 최신순 (기간 필터링 후 다시 정렬 가능)
                )

            if google_reviews:
                st.success(f"총 {len(google_reviews)}개의 리뷰를 가져왔습니다.")

                # DataFrame 생성
                df_google = pd.DataFrame(google_reviews)

                # 'at' 컬럼을 datetime 객체로 변환 (시간대 정보가 있을 수 있으므로 astimezone 사용)
                # errors='coerce'를 사용하여 변환 불가능한 값은 NaT로 처리
                df_google['at'] = pd.to_datetime(df_google['at'], errors='coerce')

                # 시간대 정보가 없는 경우 UTC로 가정하고 한국 시간대로 변환 (필요시)
                # Google Play Scraper는 기본적으로 UTC 시간을 반환합니다.
                kst = pytz.timezone('Asia/Seoul')
                df_google['at'] = df_google['at'].dt.tz_convert(kst)


                # 기간 필터링
                # date_input에서 반환되는 date 객체를 datetime 객체로 변환하여 비교
                # 시작일은 해당 날짜의 00:00:00, 종료일은 해당 날짜의 23:59:59로 간주
                start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=kst)
                end_datetime = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=kst)

                df_filtered = df_google[
                    (df_google['at'] >= start_datetime) & (df_google['at'] <= end_datetime)
                ].copy() # 필터링 결과 복사

                # 최신순으로 다시 정렬 (reviews_all의 sort와 별개로 필터링 결과 정렬)
                df_filtered = df_filtered.sort_values(by='at', ascending=False)

                # 필요한 컬럼 선택 및 이름 변경
                df_google_display = df_filtered[['userName', 'score', 'at', 'content', 'replyContent', 'repliedAt']].copy()
                df_google_display.rename(columns={
                    'userName': '작성자',
                    'score': '평점',
                    'at': '리뷰 작성일',
                    'content': '리뷰 내용',
                    'replyContent': '개발자 답변',
                    'repliedAt': '답변 작성일'
                }, inplace=True)

                # 날짜/시간 컬럼 형식 지정 (이미 한국 시간대로 변환됨)
                for col in ['리뷰 작성일', '답변 작성일']:
                    df_google_display[col] = df_google_display[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('N/A')


                # 필터링된 리뷰 개수 확인 및 표시
                st.subheader(f"기간 ({start_date} ~ {end_date}) 내 리뷰")
                st.info(f"선택된 기간 내 총 {len(df_filtered)}개의 리뷰가 있습니다.")


                # 평점 분포 시각화 (필터링된 데이터 기준)
                st.subheader("평점 분포 (기간 필터링 후)")
                # 평점 컬럼이 숫자인지 확인 후 처리
                if pd.api.types.is_numeric_dtype(df_google_display['평점']):
                    score_counts = df_google_display['평점'].value_counts().sort_index()
                    st.bar_chart(score_counts)
                else:
                    st.warning("평점 데이터가 유효하지 않아 분포를 표시할 수 없습니다.")


                # 리뷰 데이터 표시 (DataFrame 또는 Expander) - 최대 표시 개수 적용
                st.subheader(f"최신 리뷰 (기간 필터링 후, 최대 {review_count_limit}개 표시)")
                # 최대 표시 개수만큼 슬라이싱하여 표시
                st.dataframe(df_google_display.head(review_count_limit), height=600, use_container_width=True) # 너비 자동 조절


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
st.markdown("⚠️ `google-play-scraper` 라이브러리는 기술적인 한계로 인해 Google Play Store의 *모든* 리뷰를 100% 가져오지 못할 수도 있습니다.")
