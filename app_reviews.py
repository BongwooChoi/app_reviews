import streamlit as st
import pandas as pd
from google_play_scraper import reviews_all, Sort, exceptions as google_exceptions
from datetime import date, timedelta
import pytz
import requests
import math
import altair as alt
import io # BytesIO 사용을 위해 import
import re # 텍스트 정제를 위해 import

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
        width: auto !important; /* 버튼 자체는 내용에 맞게 */
        display: inline-block !important; /* 컬럼 내에서 인라인 블록으로 */
        white-space: nowrap; /* 텍스트 줄바꿈 방지 */
        max-width: 100%; /* 부모 컨테이너 너비를 넘지 않도록 */
    }
    /* 버튼을 포함하는 컬럼의 너비를 더 작게 (조정) */
    .stColumns > div:last-child { /* 마지막 컬럼 (버튼 컬럼) */
        flex-grow: 0 !important; /* 남은 공간을 차지하지 않도록 */
        flex_shrink: 0 !important; /* 줄어들지 않도록 */
        /* 너비를 10%에서 20%로 조정하여 버튼 텍스트 공간 확보 */
        width: 20% !important;
        min_width: unset !important; /* 최소 너비 제한 해제 */
        display: flex; /* 내부 요소를 정렬하기 위해 flex 사용 */
        justify_content: flex-end; /* 버튼을 컬럼 오른쪽으로 정렬 */
        align_items: center; /* 세로 중앙 정렬 */
    }

    /* 총 리뷰 개수 텍스트와 다운로드 버튼이 같은 라인에 오도록 조정 */
    .stSubheader {
        display: inline-block; /* 인라인 블록으로 표시 */
        margin_right: 10px; /* 버튼과의 간격 추가 */
        vertical_align: middle; /* 세로 중앙 정렬 */
    }

    /* Streamlit 컬럼 내부의 요소들이 플렉스 아이템으로 동작하도록 설정 */
    .stColumns > div {
        display: flex;
        flex_direction: column; /* 기본 세로 방향 유지 */
    }

    /* 총 리뷰 개수와 다운로드 버튼을 담는 컨테이너에 대한 추가 스타일 */
    /* 이 부분은 Streamlit의 내부 구조에 따라 다를 수 있으므로 테스트 필요 */
     div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stSubheader"]) {
        flex_direction: row; /* 총 리뷰 개수와 버튼을 수평으로 배치 */
        align_items: center; /* 세로 중앙 정렬 */
        justify_content: space-between; /* 양 끝 정렬 */
     }


    </style>
    """,
    unsafe_allow_html=True
)

# --- 텍스트 정제 함수 ---
def clean_text_for_excel(text):
    """
    Excel 파일 저장을 위해 텍스트에서 문제가 될 수 있는 문자를 제거합니다.
    제어 문자 및 일부 특수 문자를 제거 대상으로 합니다.
    """
    if pd.isna(text):
        return text
    # 텍스트가 아닌 경우 문자열로 변환 시도
    text = str(text)
    # Excel에서 문제가 될 수 있는 제어 문자 및 일부 특수 문자 제거
    # 예: \x00 (Null), \x0b (Vertical Tab), \x0c (Form Feed) 등
    # \n (줄바꿈), \r (캐리지 리턴), \t (탭)은 유지
    cleaned_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # 추가적으로 문제가 될 수 있는 문자나 패턴이 있다면 여기에 추가하여 제거할 수 있습니다.
    # 예: cleaned_text = cleaned_text.replace('특정문자', '')
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
                # reviews_all은 기본적으로 모든 리뷰를 가져오므로, 날짜 필터링은 가져온 후에 적용합니다.
                google_reviews = reviews_all(
                    google_app_id,
                    lang='ko', country='kr', sort=Sort.NEWEST # 최신순으로 가져옵니다.
                )

            if not google_reviews:
                st.info("리뷰를 찾을 수 없습니다.")
            else:
                df_g = pd.DataFrame(google_reviews)
                # 'at' 컬럼을 datetime 형식으로 변환, 오류 발생 시 NaT 처리
                df_g['at'] = pd.to_datetime(df_g['at'], errors='coerce')
                # 유효한 날짜만 남김
                df_g = df_g[df_g['at'].notna()]

                # 날짜 필터링 적용
                if use_date_filter and selected_start_date:
                    df_g = df_g[df_g['at'].dt.date >= selected_start_date]

                if df_g.empty:
                    st.info(f"선택일 ({selected_start_date}) 이후 리뷰가 없습니다.")
                else:
                    # 표시할 컬럼 선택 및 이름 변경
                    df_g_disp = df_g[['userName','score','at','content','replyContent','repliedAt']].copy()
                    df_g_disp.columns = ['작성자','평점','리뷰 작성일','리뷰 내용','개발자 답변','답변 작성일']

                    # 시간대 변환 및 형식 지정
                    tz = pytz.timezone('Asia/Seoul')
                    for c in ['리뷰 작성일','답변 작성일']:
                        # 이미 datetime 형식이지만, 시간대 정보가 없을 수 있으므로 다시 변환
                        df_g_disp[c] = pd.to_datetime(df_g_disp[c], errors='coerce')
                        # 시간대 정보가 없는 경우 UTC로 가정하고 변환
                        df_g_disp[c] = df_g_disp[c].dt.tz_localize('UTC', ambiguous='NaT', nonexistent='NaT')
                        # 서울 시간대로 변환하고 원하는 문자열 형식으로 포맷팅, NaT는 'N/A'로 표시
                        df_g_disp[c] = df_g_disp[c].dt.tz_convert(tz).dt.strftime('%Y-%m-%d %H:%M:%S').fillna('N/A')

                    # --- 텍스트 정제 적용 (Google 리뷰) ---
                    for col in ['리뷰 내용', '개발자 답변']:
                         if col in df_g_disp.columns:
                             df_g_disp[col] = df_g_disp[col].apply(clean_text_for_excel)
                    # -----------------------------------

                    # 평점 분포 및 테이블
                    st.subheader("평점 분포")
                    # 평점별 개수를 계산하고 인덱스(평점) 기준으로 정렬
                    rating_counts_g = df_g_disp['평점'].value_counts().sort_index()
                    st.bar_chart(rating_counts_g) # Streamlit 기본 바 차트 사용

                    # "총 리뷰 개수"와 "다운로드" 버튼을 위한 레이아웃 조정
                    # st.subheader와 st.download_button을 같은 라인에 표시하기 위해 컬럼 사용
                    count_col_g, btn_col_g = st.columns([8, 2]) # 비율 조정

                    with count_col_g:
                         st.subheader(f"총 {len(df_g_disp)}개 리뷰") # 필터링된 리뷰 개수 표시

                    with btn_col_g:
                        # 엑셀 파일 생성을 위한 BytesIO 객체 생성
                        excel_buffer_g = io.BytesIO()
                        # DataFrame을 엑셀 파일로 저장 (인덱스 제외, UTF-8 인코딩은 to_excel에서 기본 처리)
                        df_g_disp.to_excel(excel_buffer_g, index=False, engine='openpyxl')
                        # 파일 포인터를 시작으로 이동
                        excel_buffer_g.seek(0)

                        # 다운로드 버튼 (엑셀 형식)
                        st.download_button(
                            label="다운로드", # 버튼 라벨 변경
                            data=excel_buffer_g, # BytesIO 객체 전달
                            file_name="google_reviews.xlsx", # 파일 이름 변경
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" # MIME 타입 변경
                            # key="google_download_button" # 필요하다면 고유 키 추가
                        )
                    st.dataframe(df_g_disp, height=500, use_container_width=True)

        except google_exceptions.NotFoundError:
            st.error(f"Google Play 앱 ID '{google_app_id}'를 찾을 수 없습니다. ID를 확인해주세요.")
        except Exception as e:
            st.error(f"Google 리뷰 로딩 오류: {e}")
            # st.exception(e) # 디버깅을 위해 상세 오류 메시지 표시 가능

# --- App Store 리뷰 ---
with col2:
    st.header("🍎 App Store 리뷰")
    if not apple_app_id:
        st.warning("App Store 앱 ID를 입력하세요.")
    else:
        try:
            with st.spinner(f"App Store ID '{apple_app_id}' 리뷰 로딩 중... (최대 {review_count_limit}건)"):
                all_reviews = []
                per_page = 50 # App Store RSS 피드는 페이지당 최대 50개 리뷰 제공
                # 요청할 페이지 수 계산 (최대 리뷰 개수와 페이지당 개수 기반)
                pages_to_fetch = math.ceil(review_count_limit / per_page)

                for page in range(1, pages_to_fetch + 1):
                    # App Store RSS 피드 URL (한국, JSON 형식)
                    url = f"https://itunes.apple.com/kr/rss/customerreviews/page={page}/id={apple_app_id}/json"
                    resp = requests.get(url)
                    resp.raise_for_status() # HTTP 오류 발생 시 예외 발생

                    data = resp.json()
                    # 'feed' -> 'entry' 경로에서 리뷰 목록 추출
                    entries = data.get('feed', {}).get('entry', [])

                    # 첫 번째 entry는 피드 정보일 수 있으므로, 실제 리뷰는 그 이후부터 시작
                    # 또는 entry가 비어있거나 1개 이하인 경우 (리뷰 없거나 피드 정보만 있는 경우) 반복 중단
                    if not entries or (page == 1 and len(entries) <= 1):
                         if page == 1: # 첫 페이지에 리뷰가 없으면 메시지 출력
                             st.info("App Store 리뷰를 찾을 수 없습니다.")
                         break # 리뷰가 더 이상 없으면 반복 중단

                    # 첫 페이지의 첫 번째 entry는 피드 정보일 가능성이 높으므로 건너뛰고, 그 외에는 모든 entry 사용
                    current_page_reviews = entries[1:] if page == 1 else entries
                    all_reviews.extend(current_page_reviews)

                    # 요청한 최대 개수에 도달했거나, 현재 페이지의 리뷰 개수가 per_page보다 작으면 더 이상 페이지가 없다고 판단
                    if len(all_reviews) >= review_count_limit or len(current_page_reviews) < per_page:
                        break # 반복 중단

                # 최종적으로 요청된 최대 개수만큼만 사용
                reviews = all_reviews[:review_count_limit]


            if not reviews:
                 # 리뷰를 찾을 수 없다는 메시지는 위에서 이미 처리했으므로 여기서는 추가 메시지 불필요
                 pass # 또는 st.info("App Store 리뷰를 찾을 수 없습니다.")

            else:
                # 리뷰 데이터를 DataFrame으로 변환
                df_a = pd.DataFrame([
                    {
                        '작성자': r.get('author', {}).get('name', {}).get('label', 'N/A'),
                        '평점': int(r.get('im:rating', {}).get('label', 0)), # 평점 없으면 0으로 처리
                        '리뷰 작성일': r.get('updated', {}).get('label', None), # 날짜 없으면 None
                        '버전': r.get('im:version', {}).get('label', 'N/A'),
                        '제목': r.get('title', {}).get('label', 'N/A'),
                        '리뷰 내용': r.get('content', {}).get('label', 'N/A')
                    }
                    for r in reviews
                ])

                # '리뷰 작성일' 컬럼을 datetime 형식으로 변환, 오류 발생 시 NaT 처리
                df_a['리뷰 작성일'] = pd.to_datetime(df_a['리뷰 작성일'], errors='coerce')
                 # 유효한 날짜만 남김
                df_a = df_a[df_a['리뷰 작성일'].notna()]

                # 날짜 필터링 적용
                if use_date_filter and selected_start_date:
                    df_a = df_a[df_a['리뷰 작성일'].dt.date >= selected_start_date]

                if df_a.empty:
                    st.info(f"선택일 ({selected_start_date}) 이후 App Store 리뷰가 없습니다.")
                else:
                    # 시간대 변환 및 형식 지정
                    tz = pytz.timezone('Asia/Seoul')
                    # App Store RSS 피드의 날짜는 보통 UTC이므로, UTC로 가정하고 변환
                    df_a['리뷰 작성일'] = df_a['리뷰 작성일'].apply(
                        lambda x: x.tz_localize('UTC', ambiguous='NaT', nonexistent='NaT') if pd.notna(x) and x.tzinfo is None else x
                    )
                     # 서울 시간대로 변환하고 원하는 문자열 형식으로 포맷팅
                    df_a['리뷰 작성일'] = df_a['리뷰 작성일'].dt.tz_convert(tz).dt.strftime('%Y-%m-%d %H:%M:%S')

                    # --- 텍스트 정제 적용 (App Store 리뷰) ---
                    for col in ['제목', '리뷰 내용']:
                         if col in df_a.columns:
                             df_a[col] = df_a[col].apply(clean_text_for_excel)
                    # -----------------------------------

                    # 평점 분포 및 테이블
                    st.subheader("평점 분포")
                    # 평점별 개수를 계산하고 인덱스(평점) 기준으로 정렬
                    rating_counts_a = df_a['평점'].value_counts().sort_index().reset_index()
                    rating_counts_a.columns = ['평점','count']
                    # Altair 차트 생성
                    chart = alt.Chart(rating_counts_a).mark_bar(color='red').encode(
                        x=alt.X('평점:O', axis=alt.Axis(title=None)), # 평점을 순서형 데이터로, 축 제목 없음
                        y=alt.Y('count:Q', axis=alt.Axis(title=None)) # 개수를 정량형 데이터로, 축 제목 없음
                    ).properties(
                        # title="App Store 평점 분포" # 필요하다면 차트 제목 추가
                    )
                    st.altair_chart(chart, use_container_width=True) # Altair 차트 표시

                    # "총 리뷰 개수"와 "다운로드" 버튼을 위한 레이아웃 조정
                    count_col_a, btn_col_a = st.columns([8, 2]) # 비율 조정

                    with count_col_a:
                         st.subheader(f"총 {len(df_a)}개 리뷰 (최대 {review_count_limit}건)") # 필터링된 리뷰 개수 표시

                    with btn_col_a:
                        # 엑셀 파일 생성을 위한 BytesIO 객체 생성
                        excel_buffer_a = io.BytesIO()
                        # DataFrame을 엑셀 파일로 저장 (인덱스 제외)
                        df_a.to_excel(excel_buffer_a, index=False, engine='openpyxl')
                         # 파일 포인터를 시작으로 이동
                        excel_buffer_a.seek(0)

                        # 다운로드 버튼 (엑셀 형식)
                        st.download_button(
                            label="다운로드", # 버튼 라벨 변경
                            data=excel_buffer_a, # BytesIO 객체 전달
                            file_name="apple_reviews.xlsx", # 파일 이름 변경
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" # MIME 타입 변경
                            # key="apple_download_button" # 필요하다면 고유 키 추가
                        )
                    st.dataframe(df_a, height=500, use_container_width=True)

        except requests.exceptions.RequestException as e:
             st.error(f"App Store RSS 피드 요청 오류: {e}")
        except Exception as e:
            st.error(f"App Store 리뷰 로딩 오류: {e}")
            # st.exception(e) # 디버깅을 위해 상세 오류 메시지 표시 가능

# --- 하단 출처 ---
st.divider()
st.markdown("데이터 출처: google-play-scraper, iTunes RSS API with pagination")
