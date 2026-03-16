import streamlit as st
from google import genai
from openai import OpenAI
import speech_recognition as sr
import random

# 1. 페이지 설정
st.set_page_config(page_title="AI 대본 생성기", layout="wide")

from streamlit_javascript import st_javascript

def get_local_storage(key):
    return st_javascript(f"localStorage.getItem('{key}');")

def set_local_storage(key, val):
    st_javascript(f"localStorage.setItem('{key}', '{val}');")

def clear_local_storage(key):
    st_javascript(f"localStorage.removeItem('{key}');")

# 카테고리 및 가이드 데이터
CATEGORIES = {
    "애니메이션": ["판타지", "액션", "일상", "로맨스", "SF", "코미디", "스포츠", "시대극"],
    "내레이션": ["다큐멘터리", "드라마", "오디오북"],
    "게임": [],
    "광고": ["상업광고", "공익광고", "기업홍보"],
    "라디오 드라마": [],
    "어색한 대본": []
}

GENRE_GUIDES = {
    "애니메이션": "캐릭터 개성 극대화, 감정 진폭이 큰 연기 중심.",
    "내레이션": "신뢰감 있는 톤, 정확한 정보 전달과 절제된 호흡.",
    "게임": "짧고 강렬한 임팩트, 시네마틱한 말투.",
    "광고": "청각적 훅(Hook) 중심, 빠르고 정확한 딕션.",
    "라디오 드라마": "목소리만으로 공간감을 만드는 일상 연기.",
    "어색한 대본": "순발력과 발음 교정 훈련용."
}

AI_PROVIDERS = ["Google Gemini", "OpenAI (ChatGPT)", "기타 / 로컬 AI (OpenAI 호환)"]

# 세션 상태 초기화
if "current_script" not in st.session_state:
    st.session_state.current_script = ""
if "prev_main_category" not in st.session_state:
    st.session_state.prev_main_category = "랜덤 선택"
if "show_manage_keys" not in st.session_state:
    st.session_state.show_manage_keys = False
if "custom_url" not in st.session_state:
    st.session_state.custom_url = ""

# --- 2. 상단 헤더 및 AI 설정 (Popover) ---
col_title, col_setup = st.columns([4, 1])

with col_title:
    st.title("🎙️ AI 대본 생성기")

with col_setup:
    with st.popover("⚙️ AI 설정"):
        ai_provider = st.selectbox("사용할 AI 서비스", AI_PROVIDERS)

        # 로컬 AI 전용 설정 (Base URL)
        if ai_provider == "기타 / 로컬 AI (OpenAI 호환)":
            st.session_state.custom_url = st.text_input(
                "API Base URL",
                value=st.session_state.custom_url,
                placeholder="예: http://localhost:11434/v1"
            )

        # ✅ 핵심 변경: 파일 대신 localStorage에서만 키를 읽어옴
        storage_key = f"api_key_{ai_provider}"
        stored_key_raw = get_local_storage(storage_key)

        # localStorage는 값이 없을 때 0 또는 None을 반환하므로 문자열인지 확인
        if isinstance(stored_key_raw, str) and stored_key_raw.strip():
            current_key = stored_key_raw.strip()
        else:
            current_key = ""

        st.write("---")
        st.markdown("### 🔑 API 키 관리")

        if current_key:
            st.success(f"✅ 키 등록됨: `{current_key[:6]}...{current_key[-4:]}`")
            st.caption("이 키는 내 브라우저에만 저장됩니다. 다른 사람과 공유되지 않습니다.")

            col_a, col_b = st.columns([1, 1])
            with col_a:
                if st.button("🗑️ 키 삭제", use_container_width=True):
                    clear_local_storage(storage_key)
                    st.rerun()
            with col_b:
                if st.button("🔄 키 교체", use_container_width=True):
                    st.session_state.show_manage_keys = True
        else:
            st.info("등록된 키가 없습니다. 아래에서 키를 추가하세요.")
            st.session_state.show_manage_keys = True

        if st.session_state.show_manage_keys or not current_key:
            new_key = st.text_input("새 API 키 입력", type="password", placeholder="sk-... 또는 AIza...")
            if st.button("➕ 등록하기", use_container_width=True):
                if new_key and new_key.strip():
                    set_local_storage(storage_key, new_key.strip())
                    st.session_state.show_manage_keys = False
                    st.rerun()
                else:
                    st.warning("키를 입력해주세요.")

        # 모델 선택
        st.write("---")
        if ai_provider == "Google Gemini":
            selected_model = st.selectbox("모델", ["gemini-2.5-flash", "gemini-2.0-flash"])
        elif ai_provider == "OpenAI (ChatGPT)":
            selected_model = st.selectbox("모델", ["gpt-4o-mini", "gpt-4o"])
        else:
            selected_model = st.text_input(
                "모델 명칭",
                value="llama3",
                placeholder="사용할 모델 이름을 입력하세요"
            )

# --- 3. 사이드바: 대본 설정 ---
with st.sidebar:
    st.markdown("### 🎭 대본 설정")
    user_gender = st.radio("나의 성별", ["남성", "여성"], horizontal=True)
    main_cat_list = ["랜덤 선택"] + list(CATEGORIES.keys())
    main_category = st.selectbox("🎯 대분류 선택", main_cat_list)

    if main_category != st.session_state.prev_main_category:
        st.session_state.current_script = ""
        st.session_state.prev_main_category = main_category

    sub_category = None
    if main_category != "랜덤 선택":
        sub_items = CATEGORIES.get(main_category, [])
        if sub_items:
            sub_category = st.selectbox("📂 세부 항목", ["랜덤"] + sub_items)

    has_partner = main_category in ["애니메이션", "라디오 드라마"] and st.checkbox("상대 배역 포함", value=True)

# --- 4. AI 호출 함수 ---
def call_ai(prompt):
    # ✅ 핵심 변경: localStorage에서 읽은 키를 세션 상태로 전달받아 사용
    key = st.session_state.get("_current_api_key", "")
    if not key:
        return None

    try:
        if ai_provider == "Google Gemini":
            client = genai.Client(api_key=key)
            res = client.models.generate_content(model=selected_model, contents=prompt).text
        elif ai_provider == "OpenAI (ChatGPT)":
            client = OpenAI(api_key=key)
            res = client.chat.completions.create(
                model=selected_model,
                messages=[{"role": "user", "content": prompt}]
            ).choices[0].message.content
        else:  # 로컬 AI
            client = OpenAI(api_key=key, base_url=st.session_state.custom_url)
            res = client.chat.completions.create(
                model=selected_model,
                messages=[{"role": "user", "content": prompt}]
            ).choices[0].message.content
        return res
    except Exception as e:
        error_msg = str(e)
        if "auth" in error_msg.lower() or "api key" in error_msg.lower() or "invalid" in error_msg.lower():
            return "API_KEY_INVALID"
        elif "quota" in error_msg.lower() or "limit" in error_msg.lower():
            return "API_QUOTA_EXHAUSTED"
        else:
            return f"API_ERROR:{error_msg}"

# 현재 키를 세션에 저장 (call_ai에서 사용하기 위해)
if current_key:
    st.session_state["_current_api_key"] = current_key
else:
    st.session_state["_current_api_key"] = ""

# --- 5. 대본 생성 메인 로직 ---
if not current_key:
    st.warning("⚙️ 오른쪽 상단의 **AI 설정**에서 API 키를 먼저 등록해주세요.")
else:
    if st.button("✨ 새로운 대본 생성하기", use_container_width=True):
        final_main = main_category if main_category != "랜덤 선택" else random.choice(list(CATEGORIES.keys()))
        final_sub = sub_category if sub_category not in ["랜덤", None] else (
            random.choice(CATEGORIES[final_main]) if CATEGORIES[final_main] else ""
        )
        sub_text = f"({final_sub})" if final_sub else ""
        p_style = "2인극" if has_partner else "1인극"
        genre_guide = GENRE_GUIDES.get(final_main, "")

        prompt = f"""
성우 공채 전문 작가로서 [{final_main}] 장르 대본을 집필하라.
장르: {final_main} {sub_text}, 스타일: {p_style}.

[작성 지침]:
1. 캐릭터 설정: **이름 (나이, 성별, 외형, 말투)** 형식으로 한 줄 요약하라.
2. 대사는 7~10줄 내외로 작성하며 호흡 단위로 빈번하게 줄바꿈(\\n\\n)하라.
3. 지문은 `:gray[*(지문)*]` 형식으로 1~2단어 이내로만, 대본 전체에서 2~3회만 아주 드물게 사용하라.
4. 이름 색상: 2인극일 경우 첫 번째 캐릭터는 **:blue[이름]**, 두 번째 캐릭터는 **:green[이름]**으로 표시하라. 1인극은 **:blue[이름]**만 사용.
5. HTML 태그 사용 금지. {genre_guide}

양식:
### 📋 캐릭터 정보
### 📖 연습 대본
"""
        with st.spinner("AI가 연습용 대본을 생성중입니다..."):
            result = call_ai(prompt)
            if result is None:
                st.error("API 키가 없습니다. AI 설정에서 키를 등록해주세요.")
            elif result == "API_KEY_INVALID":
                st.error("🔑 API 키가 올바르지 않습니다. AI 설정에서 키를 확인해주세요.")
            elif result == "API_QUOTA_EXHAUSTED":
                st.error("🚫 API 사용량이 초과되었습니다. 잠시 후 다시 시도해주세요.")
            elif result.startswith("API_ERROR:"):
                st.error(f"오류 발생: {result.replace('API_ERROR:', '')}")
            else:
                st.session_state.current_script = result
                st.rerun()

if st.session_state.current_script:
    st.markdown(st.session_state.current_script)
    st.divider()
    st.markdown("### 🎤 내 낭독 인식 내용")
    audio_value = st.audio_input("연습 녹음")
    if audio_value:
        try:
            r = sr.Recognizer()
            with sr.AudioFile(audio_value) as source:
                audio_data = r.record(source)
            recognized = r.recognize_google(audio_data, language='ko-KR')
            st.write(f"🗣️ **인식 내용:** {recognized}")
        except sr.UnknownValueError:
            st.error("음성을 인식하지 못했습니다. 더 크고 명확하게 말씀해주세요.")
        except sr.RequestError:
            st.error("음성 인식 서버에 연결할 수 없습니다. 인터넷 연결을 확인해주세요.")
        except Exception as e:
            st.error(f"오류 발생: {str(e)}")