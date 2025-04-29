import streamlit as st
import pandas as pd
from google_play_scraper import reviews_all, Sort, exceptions as google_exceptions
# from app_store_scraper import AppStore # app-store-scraper 대신 requests-html 사용
from requests_html import HTMLSession # requests-html 라이브러리 임포트
from datetime import datetime
import pytz # 시간대 처리를 위해 pytz 추가
import time # JavaScript 렌더링 대기를 위해 time 모듈 사용

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
# App Store 앱 이름 입력 필드 (requests-html 방식에서는 URL 구성에 직접 사용되지는 않지만 정보 제공용으로 유지)
app_store_app_name = st.sidebar.text_input("App Store 앱 이름", "kb라이프생명") # 앱 이름 기본값 설정 (소문자 kb)
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
    # 앱 ID와 국가 코드가 모두 입력되었는지 확인
    if app_store_app_id and app_store_country:
        # 앱 ID가 숫자로만 구성되었는지 확인 (기본적인 유효성 검사)
        if app_store_app_id.isdigit():
            # App Store URL 구성 (앱 이름 부분은 URL 인코딩 필요 또는 ID만 사용)
            # 여기서는 ID만 사용하여 URL을 구성하고, requests-html로 페이지를 가져온 후 파싱합니다.
            # 앱 이름은 정보 제공용으로만 사용합니다.
            app_url = f"https://apps.apple.com/{app_store_country}/app/id{app_store_app_id}" # ID만 사용한 URL

            session = HTMLSession()
            app_store_reviews = []

            try:
                with st.spinner(f"App Store 앱 ID '{app_store_app_id}' ({app_store_country}) 리뷰 로딩 중 (requests-html)..."):
                    # 페이지 가져오기
                    r = session.get(app_url)

                    if r.status_code == 200:
                        # JavaScript 렌더링 (동적으로 로딩되는 리뷰를 가져오기 위해 필요)
                        # sleep 시간을 조절하여 리뷰 로딩을 충분히 기다립니다.
                        # timeout은 렌더링 최대 대기 시간입니다.
                        try:
                            r.html.render(sleep=5, timeout=20) # 5초 대기, 최대 20초 타임아웃
                        except Exception as render_e:
                            st.warning(f"JavaScript 렌더링 중 오류 발생 또는 타임아웃: {render_e}. 일부 리뷰가 누락될 수 있습니다.")
                            # 렌더링 오류가 나더라도 일단 현재 HTML로 파싱 시도

                        # HTML 파싱 및 리뷰 데이터 추출
                        # App Store 페이지 구조에 따라 셀렉터는 변경될 수 있습니다.
                        # 현재는 '.we-customer-review' 클래스를 가진 요소를 리뷰 컨테이너로 가정합니다.
                        review_elements = r.html.find('.we-customer-review')

                        if review_elements:
                            for i, review_el in enumerate(review_elements):
                                if i >= review_count_limit: # 설정된 최대 리뷰 개수만큼만 처리
                                    break
                                try:
                                    # 각 리뷰 요소에서 필요한 정보 추출 (셀렉터 확인 필요)
                                    user_name_el = review_el.find('.we-customer-review__user', first=True)
                                    rating_el = review_el.find('.we-customer-review__star-rating', first=True) # 평점 요소
                                    date_el = review_el.find('.we-customer-review__date', first=True)
                                    title_el = review_el.find('.we-customer-review__title', first=True)
                                    content_el = review_el.find('.we-customer-review__text', first=True)

                                    user_name = user_name_el.text if user_name_el else 'N/A'
                                    # 평점은 aria-label 속성에서 추출하는 경우가 많습니다. 예: "5 out of 5 stars"
                                    rating_text = rating_el.attrs.get('aria-label', 'N/A') if rating_el else 'N/A'
                                    date_text = date_el.text if date_el else 'N/A'
                                    title_text = title_el.text if title_el else 'N/A'
                                    content_text = content_el.text if content_el else 'N/A'

                                    app_store_reviews.append({
                                        'userName': user_name,
                                        'rating': rating_text,
                                        'date': date_text,
                                        'title': title_text,
                                        'review': content_text
                                    })
                                except Exception as parse_e:
                                    # 특정 리뷰 요소 파싱 중 오류 발생 시 건너뛰기
                                    # st.warning(f"리뷰 요소 파싱 중 오류 발생: {parse_e}") # 디버깅 시 주석 해제
                                    continue # 다음 리뷰로 이동

                        if app_store_reviews:
                            st.success(f"총 {len(app_store_reviews)}개의 리뷰를 가져왔습니다 (최대 {review_count_limit}개).")
                            # DataFrame 생성 및 필요한 컬럼 선택, 날짜 형식 변환
                            df_apple = pd.DataFrame(app_store_reviews)
                            df_apple_display = df_apple[['userName', 'rating', 'date', 'title', 'review']].copy()
                            df_apple_display.rename(columns={
                                'userName': '작성자',
                                'rating': '평점',
                                'date': '리뷰 작성일',
                                'title': '리뷰 제목',
                                'review': '리뷰 내용'
                            }, inplace=True)

                            # 날짜/시간 컬럼 형식 지정 (requests-html은 문자열로 가져올 가능성 높음)
                            # 가져온 날짜 문자열 형식이 다양할 수 있으므로, pd.to_datetime의 errors='coerce' 사용
                            kst = pytz.timezone('Asia/Seoul')
                            df_apple_display['리뷰 작성일'] = pd.to_datetime(df_apple_display['리뷰 작성일'], errors='coerce')
                            # 시간대 정보가 없는 경우 UTC로 가정하고 변환 (필요시)
                            # if df_apple_display['리뷰 작성일'].dt.tz is None:
                            #      df_apple_display['리뷰 작성일'] = df_apple_display['리뷰 작성일'].dt.tz_localize('UTC')
                            # df_apple_display['리뷰 작성일'] = df_apple_display['리뷰 작성일'].dt.tz_convert(kst)
                            # 변환 후 원하는 문자열 형식으로 포맷팅 (NaT 처리 포함)
                            df_apple_display['리뷰 작성일'] = df_apple_display['리뷰 작성일'].dt.strftime('%Y-%m-%d %H:%M:%S').fillna('N/A')


                            # 평점 분포 시각화 (선택 사항)
                            st.subheader("평점 분포")
                            # 평점 컬럼이 숫자인지 확인 후 처리 ('5 out of 5 stars' 형태일 수 있으므로 숫자만 추출 필요)
                            try:
                                # '5 out of 5 stars' 형태에서 숫자 '5'만 추출 시도
                                df_apple_display['평점_숫자'] = df_apple_display['평점'].astype(str).str.extract(r'(\d+) out of \d+ stars').astype(float)
                                if pd.api.types.is_numeric_dtype(df_apple_display['평점_숫자']):
                                    score_counts_apple = df_apple_display['평점_숫자'].value_counts().sort_index()
                                    st.bar_chart(score_counts_apple)
                                else:
                                     st.warning("평점 데이터 추출 후 분포 표시 중 오류 발생.")
                            except Exception as score_e:
                                st.warning(f"평점 데이터 처리 중 오류 발생: {score_e}. 분포를 표시할 수 없습니다.")


                            # 리뷰 데이터 표시
                            st.subheader(f"최신 리뷰 (최대 {review_count_limit}개)")
                            # 평점 숫자 컬럼은 표시하지 않음
                            st.dataframe(df_apple_display.drop(columns=['평점_숫자'], errors='ignore'), height=600, use_container_width=True) # 너비 자동 조절

                        else:
                            st.info(f"App Store 앱 ID '{app_store_app_id}' ({app_store_country})에 대한 리뷰를 찾을 수 없습니다.")
                            st.info("팁: App Store 페이지 구조가 변경되었거나, 동적 로딩이 완료되지 않았거나, 해당 앱에 리뷰가 없을 수 있습니다.")

                    else:
                         st.error(f"App Store 페이지를 가져오지 못했습니다. 상태 코드: {r.status_code}")
                         st.info("App Store 앱 ID 또는 국가 코드를 확인하거나 네트워크 상태를 점검하세요.")

            except Exception as e:
                # requests-html 관련 오류 포함
                st.error(f"App Store 리뷰 로딩 중 오류 발생: {e}")
                st.exception(e) # 상세 오류 로그 출력
                st.info("팁: requests-html 설치 및 Chromium 브라우저 사용 가능 여부를 확인하세요.")

            finally:
                if session:
                    session.close() # 세션 닫기

        else:
            st.error("App Store 앱 ID는 숫자로만 입력해주세요.")
    else:
        st.warning("App Store 앱 ID와 국가 코드를 입력해주세요.")

# --- 하단 설명 ---
st.divider()
st.markdown("데이터 출처: `google-play-scraper`, `requests-html` 라이브러리")
st.markdown("⚠️ App Store 리뷰는 웹 스크래핑 방식의 한계로 인해 불안정하거나 일부 리뷰가 누락될 수 있습니다.")
